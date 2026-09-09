from __future__ import annotations

import statistics
import torch
import torch.nn.functional as F

from src.visual.core import extract_image_urls, load_image, SigLIP2Encoder


def _aggregate_topk(values: list[float], top_k: int) -> float | None:
    values = sorted([float(x) for x in values if x is not None], reverse=True)
    if not values:
        return None
    k = max(1, min(int(top_k), len(values)))
    return sum(values[:k]) / k


def _account_embedding(image_embeddings: torch.Tensor) -> torch.Tensor | None:
    if image_embeddings is None or image_embeddings.numel() == 0:
        return None
    return F.normalize(image_embeddings.mean(dim=0, keepdim=True), p=2, dim=-1)


def _cos(a, b) -> float | None:
    if a is None or b is None:
        return None
    return float(F.cosine_similarity(a, b, dim=-1).item())


def rank_candidates_visual(
    candidates,
    item_by_username,
    seed_usernames,
    cfg,
    reference_cfg=None,
    negative_usernames=None,
):
    """
    v0.8 visual reference matching.

    Positive References define the desired visual taste.
    Optional Negative References define known off-target examples.

    No gender/identity is inferred from faces. The gate only measures whether
    the account's overall visual pattern is closer to positive or negative
    marketer-provided reference examples.
    """
    reference_cfg = reference_cfg or {}
    negative_usernames = list(negative_usernames or [])

    model_name = cfg.get("model_name", "google/siglip2-base-patch16-224")
    batch_size = int(cfg.get("batch_size", 8))
    images_per_account = int(cfg.get("images_per_account", 6))
    timeout = int(cfg.get("request_timeout_seconds", 15))
    top_k_refs = int(reference_cfg.get("top_k_references", 2))

    reference_score_weight = float(cfg.get("reference_score_weight", 0.70))
    consistency_weight = float(cfg.get("consistency_weight", 0.30))

    encoder = SigLIP2Encoder(model_name=model_name, batch_size=batch_size)

    account_embeddings = {}
    image_embeddings_by_user = {}

    usernames = list(dict.fromkeys(
        [c.username for c in candidates]
        + list(seed_usernames)
        + negative_usernames
    ))

    for idx, username in enumerate(usernames, start=1):
        item = item_by_username.get(username.lower(), {})
        urls = extract_image_urls(item, images_per_account)

        images = []
        for url in urls:
            img = load_image(url, timeout)
            if img is not None:
                images.append(img)

        if images:
            image_embeddings = encoder.encode_images(images)
            emb = _account_embedding(image_embeddings)
            if emb is not None:
                account_embeddings[username.lower()] = emb
                image_embeddings_by_user[username.lower()] = image_embeddings

        print(f"  visual {idx}/{len(usernames)} {username}: {len(images)} images")

    positive_refs = {
        s.lower(): account_embeddings[s.lower()]
        for s in seed_usernames
        if s.lower() in account_embeddings
    }
    negative_refs = {
        s.lower(): account_embeddings[s.lower()]
        for s in negative_usernames
        if s.lower() in account_embeddings
    }

    if not positive_refs:
        raise RuntimeError("Could not build positive Reference visual embeddings.")

    for c in candidates:
        key = c.username.lower()
        candidate_emb = account_embeddings.get(key)
        candidate_images = image_embeddings_by_user.get(key)

        if candidate_emb is None:
            c.visual_similarity = None
            continue

        pos_scores = []
        for ref_name, ref_emb in positive_refs.items():
            score = _cos(candidate_emb, ref_emb)
            if score is not None:
                pos_scores.append((score, ref_name))
        pos_scores.sort(reverse=True)

        c.visual_reference_similarity = _aggregate_topk(
            [x[0] for x in pos_scores], top_k_refs
        )
        c.nearest_visual_reference = pos_scores[0][1] if pos_scores else ""

        neg_scores = []
        for ref_name, ref_emb in negative_refs.items():
            score = _cos(candidate_emb, ref_emb)
            if score is not None:
                neg_scores.append((score, ref_name))
        neg_scores.sort(reverse=True)
        c.visual_negative_similarity = _aggregate_topk(
            [x[0] for x in neg_scores], top_k_refs
        )

        if (
            c.visual_reference_similarity is not None
            and c.visual_negative_similarity is not None
        ):
            c.visual_target_margin = (
                c.visual_reference_similarity - c.visual_negative_similarity
            )

        # Account-level consistency: compare each recent post to all positive
        # references and use the median best-match score.
        per_post_best = []
        if candidate_images is not None:
            for image_vec in candidate_images:
                image_vec = image_vec.unsqueeze(0)
                scores = [_cos(image_vec, ref_emb) for ref_emb in positive_refs.values()]
                scores = [x for x in scores if x is not None]
                if scores:
                    per_post_best.append(max(scores))

        c.visual_post_median_similarity = (
            float(statistics.median(per_post_best))
            if per_post_best else None
        )

        parts = []
        if c.visual_reference_similarity is not None:
            parts.append((c.visual_reference_similarity, reference_score_weight))
        if c.visual_post_median_similarity is not None:
            parts.append((c.visual_post_median_similarity, consistency_weight))

        denom = sum(w for _, w in parts)
        c.visual_similarity = (
            sum(score * weight for score, weight in parts) / denom
            if denom else None
        )

    ranked = sorted(
        candidates,
        key=lambda c: (
            c.visual_similarity is not None,
            c.visual_similarity if c.visual_similarity is not None else -1,
        ),
        reverse=True,
    )
    for rank, c in enumerate(ranked, start=1):
        c.visual_rank = rank
    return ranked
