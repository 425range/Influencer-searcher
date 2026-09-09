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



DEFAULT_TOPIC_PROMPTS = {
    "fitness": "운동 헬스 러닝 필라테스 요가 스포츠 피트니스 콘텐츠",
    "selfcare": "자기관리 웰니스 건강관리 식단 루틴 라이프스타일 콘텐츠",
    "fashion": "패션 스타일링 코디 데일리룩 의류 패션 콘텐츠",
    "beauty": "뷰티 메이크업 스킨케어 화장품 미용 콘텐츠",
    "office": "직장인 회사 출근 퇴근 오피스 커리어 일상 콘텐츠",
    "travel": "여행 호텔 해외여행 국내여행 관광 휴가 콘텐츠",
    "food": "맛집 음식 요리 카페 디저트 먹방 콘텐츠",
    "parenting": "육아 아이 아기 가족 키즈 부모 콘텐츠",
    "couple": "연애 커플 데이트 여자친구 남자친구 부부 관계 콘텐츠",
    "entertainment": "방송 예능 연예인 출연자 셀럽 엔터테인먼트 콘텐츠",
}


def _aggregate_reference_scores(scores: list[tuple[float, str]], top_k: int):
    scores = sorted(scores, key=lambda x: x[0], reverse=True)
    if not scores:
        return None, ""
    k = max(1, min(int(top_k), len(scores)))
    return sum(x[0] for x in scores[:k]) / k, scores[0][1]


def _topic_profile(account_emb, topic_embeddings, topic_names):
    if account_emb is None or topic_embeddings is None or not len(topic_names):
        return None
    sims = torch.matmul(
        F.normalize(account_emb, p=2, dim=-1),
        F.normalize(topic_embeddings, p=2, dim=-1).T,
    ).squeeze(0)
    # Raw E5 cosine scores tend to have a high common baseline. Centering the
    # topic vector makes the RELATIVE topic pattern matter more than the
    # absolute cosine level.
    centered = sims - sims.mean()
    norm = centered.norm(p=2)
    if float(norm) < 1e-8:
        return None
    return centered / norm


def _topic_profile_similarity(a, b):
    if a is None or b is None:
        return None
    # cosine [-1,1] -> [0,1]
    value = float(torch.dot(a, b).item())
    return max(0.0, min(1.0, (value + 1.0) / 2.0))


def _topic_profile_text(profile, topic_names):
    if profile is None:
        return ""
    pairs = sorted(
        zip(topic_names, profile.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )
    return ", ".join(f"{name}:{score:.3f}" for name, score in pairs[:5])


def rank_candidates_text(
    candidates,
    item_by_username: dict,
    posts_by_username: dict,
    seed_usernames: list[str],
    cfg: dict,
    ad_keywords: list[str],
    reference_cfg: dict | None = None,
    negative_usernames: list[str] | None = None,
):
    """
    v0.8:
    - raw caption similarity remains diagnostic only
    - topic-profile similarity becomes the main content signal
    - missing captions remain missing (not zero)
    - optional negative references create a positive-vs-negative margin
    """
    reference_cfg = reference_cfg or {}
    negative_usernames = list(negative_usernames or [])
    top_k_refs = int(reference_cfg.get("top_k_references", 2))

    model_name = cfg.get("model_name", "intfloat/multilingual-e5-small")
    batch_size = int(cfg.get("batch_size", 16))
    max_length = int(cfg.get("max_length", 512))
    cache_path = Path(cfg.get("cache_path", "cache/text_embeddings.pt"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    topic_prompts = cfg.get("topic_prompts", {}) or DEFAULT_TOPIC_PROMPTS
    topic_names = list(topic_prompts.keys())
    topic_texts = [topic_prompts[name] for name in topic_names]

    cache = {}
    if cache_path.exists():
        try:
            cache = torch.load(cache_path, map_location="cpu", weights_only=False)
        except Exception:
            cache = {}

    payloads = {}
    usernames = list(dict.fromkeys(
        [c.username for c in candidates]
        + list(seed_usernames)
        + negative_usernames
    ))
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
            print(f"  text {idx}/{len(usernames)} {username}: no usable text, posts={selected_count}")
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

    # Encoder may not have been created if every account came from cache.
    if topic_texts:
        if encoder is None:
            encoder = E5TextEncoder(model_name, batch_size=batch_size, max_length=max_length)
        topic_embeddings = encoder.encode(topic_texts)
    else:
        topic_embeddings = None

    topic_profiles = {
        key: _topic_profile(emb, topic_embeddings, topic_names)
        for key, emb in embeddings.items()
    }

    positive_embeddings = {
        s.lower(): embeddings[s.lower()]
        for s in seed_usernames if s.lower() in embeddings
    }
    positive_topics = {
        s.lower(): topic_profiles.get(s.lower())
        for s in seed_usernames if topic_profiles.get(s.lower()) is not None
    }
    positive_hashtags = {
        s.lower(): hashtags.get(s.lower(), set()) for s in seed_usernames
    }

    negative_topics = {
        s.lower(): topic_profiles.get(s.lower())
        for s in negative_usernames if topic_profiles.get(s.lower()) is not None
    }

    all_reference_tags = (
        set().union(*positive_hashtags.values()) if positive_hashtags else set()
    )

    for c in candidates:
        key = c.username.lower()
        candidate_emb = embeddings.get(key)
        candidate_topic = topic_profiles.get(key)

        # Legacy/raw caption score is retained only for diagnostics.
        caption_scores = []
        if candidate_emb is not None:
            for ref_name, ref_emb in positive_embeddings.items():
                score = _cosine(candidate_emb, ref_emb)
                if score is not None:
                    caption_scores.append((score, ref_name))
        c.caption_similarity, c.nearest_text_reference = _aggregate_reference_scores(
            caption_scores, top_k_refs
        )

        # Topic-profile similarity (relative distribution, not raw cosine).
        topic_scores = []
        for ref_name, ref_profile in positive_topics.items():
            score = _topic_profile_similarity(candidate_topic, ref_profile)
            if score is not None:
                topic_scores.append((score, ref_name))
        c.topic_similarity, _ = _aggregate_reference_scores(topic_scores, top_k_refs)

        neg_topic_scores = []
        for ref_name, ref_profile in negative_topics.items():
            score = _topic_profile_similarity(candidate_topic, ref_profile)
            if score is not None:
                neg_topic_scores.append((score, ref_name))
        c.topic_negative_similarity, _ = _aggregate_reference_scores(
            neg_topic_scores, top_k_refs
        )

        if c.topic_similarity is not None and c.topic_negative_similarity is not None:
            c.topic_target_margin = c.topic_similarity - c.topic_negative_similarity

        c.topic_profile = _topic_profile_text(candidate_topic, topic_names)

        candidate_tags = hashtags.get(key, set())
        hashtag_scores = []
        for ref_name, ref_tags in positive_hashtags.items():
            score = _jaccard(candidate_tags, ref_tags)
            if score is not None:
                hashtag_scores.append((score, ref_name))
        c.hashtag_similarity, c.nearest_hashtag_reference = _aggregate_reference_scores(
            hashtag_scores, top_k_refs
        )

        c.shared_hashtags = ", ".join(sorted(candidate_tags & all_reference_tags))
        c.text_posts_used = posts_used.get(key, 0)

        # v0.8 content score: Topic first, hashtag second. Raw caption cosine is
        # intentionally excluded from the default ranking because it clustered
        # around ~0.97 in the previous real-world test.
        parts = []
        if c.topic_similarity is not None:
            parts.append((c.topic_similarity, 0.85))
        if c.hashtag_similarity is not None:
            parts.append((c.hashtag_similarity, 0.15))

        denom = sum(w for _, w in parts)
        c.content_similarity = (
            sum(score * w for score, w in parts) / denom if denom else None
        )

    return candidates


def rank_candidates_combined(candidates, cfg: dict):
    """
    v0.8 dynamic ranking.

    Default:
      Visual 60%
      Topic profile 25%
      Hashtag 10%
      Graph 5%

    Raw caption cosine is NOT used by default.
    Missing signals are removed and remaining weights are re-normalized.
    """
    weights = cfg.get("weights", {}) or {}
    visual_weight = float(weights.get("visual", 0.60))
    topic_weight = float(weights.get("topic", 0.25))
    hashtag_weight = float(weights.get("hashtag", 0.10))
    graph_weight = float(weights.get("graph", 0.05))
    caption_weight = float(weights.get("caption", 0.0))

    for c in candidates:
        parts = []
        if c.visual_similarity is not None:
            parts.append(("visual", c.visual_similarity, visual_weight))
        if c.topic_similarity is not None:
            parts.append(("topic", c.topic_similarity, topic_weight))
        if c.hashtag_similarity is not None:
            parts.append(("hashtag", c.hashtag_similarity, hashtag_weight))
        if c.graph_similarity is not None:
            parts.append(("graph", c.graph_similarity, graph_weight))
        if caption_weight > 0 and c.caption_similarity is not None:
            parts.append(("caption_raw", c.caption_similarity, caption_weight))

        active = [(name, score, w) for name, score, w in parts if w > 0]
        denom = sum(w for _, _, w in active)

        c.combined_similarity = (
            sum(score * w for _, score, w in active) / denom if denom else None
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
