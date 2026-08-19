from __future__ import annotations

import hashlib
import re
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer


HASHTAG_RE = re.compile(r"(?<!\w)#([0-9A-Za-z가-힣_]+)")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@[0-9A-Za-z._]+")


def extract_hashtags(text: str) -> list[str]:
    return [m.group(1).lower() for m in HASHTAG_RE.finditer(text or "")]


def clean_caption(text: str, ad_keywords: list[str]) -> str:
    value = text or ""
    value = URL_RE.sub(" ", value)
    value = MENTION_RE.sub(" ", value)
    value = HASHTAG_RE.sub(" ", value)
    for keyword in ad_keywords or []:
        value = value.replace(keyword, " ")
        value = value.replace(keyword.lower(), " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _mean_normalized(vectors: list[torch.Tensor]) -> torch.Tensor | None:
    usable = [x for x in vectors if x is not None and x.numel()]
    if not usable:
        return None
    return F.normalize(torch.cat(usable, dim=0).mean(dim=0, keepdim=True), p=2, dim=-1)


def _cosine(a: torch.Tensor | None, b: torch.Tensor | None) -> float | None:
    if a is None or b is None:
        return None
    return float(F.cosine_similarity(a, b, dim=-1).item())


def _jaccard(a: set[str], b: set[str]) -> float | None:
    if not a or not b:
        return None
    union = a | b
    return len(a & b) / len(union) if union else None


class E5TextEncoder:
    """Small local multilingual text encoder using Transformers only."""

    def __init__(self, model_name: str, batch_size: int = 16, max_length: int = 512):
        self.model_name = model_name
        self.batch_size = int(batch_size)
        self.max_length = int(max_length)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[Text] model={model_name}")
        print(f"[Text] device={self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device).eval()

    @staticmethod
    def _average_pool(last_hidden_states, attention_mask):
        masked = last_hidden_states.masked_fill(~attention_mask[..., None].bool(), 0.0)
        return masked.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

    @torch.no_grad()
    def encode(self, texts: list[str]) -> torch.Tensor:
        if not texts:
            return torch.empty((0, 0))
        chunks = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            # E5 models expect an instruction prefix. For symmetric content
            # similarity we use the same prefix on every account/post.
            batch = [f"query: {x}" for x in batch]
            inputs = self.tokenizer(
                batch,
                max_length=self.max_length,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            emb = self._average_pool(outputs.last_hidden_state, inputs["attention_mask"])
            emb = F.normalize(emb, p=2, dim=-1)
            chunks.append(emb.cpu())
        return torch.cat(chunks, dim=0)


def _account_payload(item: dict, posts, cfg: dict, ad_keywords: list[str]):
    recent_posts = int(cfg.get("recent_posts", 8))
    include_ads = bool(cfg.get("include_ads", False))
    include_bio = bool(cfg.get("include_bio", True))
    stop_hashtags = {str(x).lower().lstrip("#") for x in cfg.get("stop_hashtags", [])}

    ordered = sorted(posts, key=lambda p: p.timestamp or "", reverse=True)
    selected = []
    for p in ordered:
        if not include_ads and p.is_ad:
            continue
        selected.append(p)
        if len(selected) >= recent_posts:
            break

    caption_docs = []
    if include_bio:
        bio = clean_caption(item.get("biography", "") if item else "", ad_keywords)
        if bio:
            caption_docs.append(bio)

    hashtag_set = set()
    for p in selected:
        cleaned = clean_caption(p.caption, ad_keywords)
        if cleaned:
            caption_docs.append(cleaned)
        for tag in extract_hashtags(p.caption):
            if tag not in stop_hashtags:
                hashtag_set.add(tag)

    return caption_docs, hashtag_set, len(selected)


def _fingerprint(model_name: str, cfg: dict, caption_docs: list[str]) -> str:
    payload = "\n".join([
        model_name,
        str(cfg.get("recent_posts", 8)),
        str(bool(cfg.get("include_ads", False))),
        str(bool(cfg.get("include_bio", True))),
        *caption_docs,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()



def _aggregate_reference_scores(scores: list[tuple[float, str]], top_k: int):
    scores = sorted(scores, key=lambda x: x[0], reverse=True)
    if not scores:
        return None, ""
    k = max(1, min(int(top_k), len(scores)))
    return sum(x[0] for x in scores[:k]) / k, scores[0][1]


def rank_candidates_text(
    candidates,
    item_by_username: dict,
    posts_by_username: dict,
    seed_usernames: list[str],
    cfg: dict,
    ad_keywords: list[str],
    reference_cfg: dict | None = None,
):
    reference_cfg = reference_cfg or {}
    top_k_refs = int(reference_cfg.get("top_k_references", 2))

    model_name = cfg.get("model_name", "intfloat/multilingual-e5-small")
    batch_size = int(cfg.get("batch_size", 16))
    max_length = int(cfg.get("max_length", 512))
    caption_weight = float(cfg.get("caption_weight", 0.8))
    hashtag_weight = float(cfg.get("hashtag_weight", 0.2))
    cache_path = Path(cfg.get("cache_path", "cache/text_embeddings.pt"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache = {}
    if cache_path.exists():
        try:
            cache = torch.load(cache_path, map_location="cpu", weights_only=False)
        except Exception:
            cache = {}

    payloads = {}
    usernames = list(dict.fromkeys([c.username for c in candidates] + list(seed_usernames)))
    for username in usernames:
        key = username.lower()
        item = item_by_username.get(key, {})
        posts = posts_by_username.get(key, [])
        payloads[key] = _account_payload(item, posts, cfg, ad_keywords)

    encoder = None
    embeddings = {}
    hashtags = {}
    posts_used = {}

    for idx, username in enumerate(usernames, start=1):
        key = username.lower()
        caption_docs, hashtag_set, selected_count = payloads[key]
        hashtags[key] = hashtag_set
        posts_used[key] = selected_count

        fp = _fingerprint(model_name, cfg, caption_docs)
        cached = cache.get(key)
        if cached and cached.get("fingerprint") == fp and cached.get("embedding") is not None:
            embeddings[key] = cached["embedding"]
            print(f"  text {idx}/{len(usernames)} {username}: cache, posts={selected_count}, tags={len(hashtag_set)}")
            continue

        if not caption_docs:
            print(f"  text {idx}/{len(usernames)} {username}: no usable caption, posts={selected_count}")
            continue

        if encoder is None:
            encoder = E5TextEncoder(model_name, batch_size=batch_size, max_length=max_length)

        doc_embeddings = encoder.encode(caption_docs)
        account_emb = _mean_normalized([doc_embeddings])
        if account_emb is not None:
            embeddings[key] = account_emb
            cache[key] = {"fingerprint": fp, "embedding": account_emb}
            torch.save(cache, cache_path)

        print(f"  text {idx}/{len(usernames)} {username}: posts={selected_count}, docs={len(caption_docs)}, tags={len(hashtag_set)}")

    reference_embeddings = {
        s.lower(): embeddings[s.lower()]
        for s in seed_usernames
        if s.lower() in embeddings
    }
    reference_hashtags = {
        s.lower(): hashtags.get(s.lower(), set())
        for s in seed_usernames
    }
    all_reference_tags = set().union(*reference_hashtags.values()) if reference_hashtags else set()

    for c in candidates:
        key = c.username.lower()

        caption_scores = []
        candidate_emb = embeddings.get(key)
        if candidate_emb is not None:
            for ref_name, ref_emb in reference_embeddings.items():
                score = _cosine(candidate_emb, ref_emb)
                if score is not None:
                    caption_scores.append((score, ref_name))

        c.caption_similarity, c.nearest_text_reference = _aggregate_reference_scores(
            caption_scores, top_k_refs
        )

        hashtag_scores = []
        candidate_tags = hashtags.get(key, set())
        for ref_name, ref_tags in reference_hashtags.items():
            score = _jaccard(candidate_tags, ref_tags)
            if score is not None:
                hashtag_scores.append((score, ref_name))

        c.hashtag_similarity, c.nearest_hashtag_reference = _aggregate_reference_scores(
            hashtag_scores, top_k_refs
        )

        c.shared_hashtags = ", ".join(sorted(candidate_tags & all_reference_tags))
        c.text_posts_used = posts_used.get(key, 0)

        available = []
        if c.caption_similarity is not None:
            available.append((c.caption_similarity, caption_weight))
        if c.hashtag_similarity is not None:
            available.append((c.hashtag_similarity, hashtag_weight))

        if available:
            denom = sum(w for _, w in available)
            c.content_similarity = sum(score * w for score, w in available) / denom if denom else None
        else:
            c.content_similarity = None

    return candidates


def rank_candidates_combined(candidates, cfg: dict):
    """
    v0.7 dynamic weighting.

    Missing captions do NOT get a zero. The remaining available signals are
    re-normalized automatically. This avoids penalizing macro accounts that
    rarely write captions.
    """
    weights = cfg.get("weights", {}) or {}

    visual_weight = float(weights.get("visual", cfg.get("visual_weight", 0.55)))
    caption_weight = float(weights.get("caption", 0.25))
    hashtag_weight = float(weights.get("hashtag", 0.10))
    graph_weight = float(weights.get("graph", 0.10))

    for c in candidates:
        parts = []

        if c.visual_similarity is not None:
            parts.append(("visual", c.visual_similarity, visual_weight))
        if c.caption_similarity is not None:
            parts.append(("caption", c.caption_similarity, caption_weight))
        if c.hashtag_similarity is not None:
            parts.append(("hashtag", c.hashtag_similarity, hashtag_weight))
        if c.graph_similarity is not None:
            parts.append(("graph", c.graph_similarity, graph_weight))

        active = [(name, score, w) for name, score, w in parts if w > 0]
        denom = sum(w for _, _, w in active)

        c.combined_similarity = (
            sum(score * w for _, score, w in active) / denom
            if denom else None
        )
        c.ranking_signals_used = ", ".join(name for name, _, _ in active)

    ranked = sorted(
        candidates,
        key=lambda c: (
            c.combined_similarity is not None,
            c.combined_similarity if c.combined_similarity is not None else -1,
            c.pre_score,
        ),
        reverse=True,
    )
    for rank, c in enumerate(ranked, start=1):
        c.combined_rank = rank

    return ranked
