def follower_fit(followers, minimum, maximum):
    if followers is None or followers < minimum or followers > maximum:
        return 0.0
    return 1.0


def category_fit(candidate, desired_categories, soft_exclude_hits=0, soft_penalty=0.10):
    categories = desired_categories or list(candidate.category_scores.keys())
    values = [candidate.category_scores.get(x, 0.0) for x in categories]
    base = sum(values) / len(values) if values else 0.0
    return max(0.0, min(1.0, base - soft_exclude_hits * soft_penalty))


def pre_score(candidate, filters, desired_categories, soft_exclude_hits=0):
    # v0.4: discovery source is not allowed to dominate the ranking.
    # This score is only a light fallback before visual ranking.
    cfit = category_fit(candidate, desired_categories, soft_exclude_hits)
    ffit = follower_fit(candidate.followers, filters["min_followers"], filters["max_followers"])
    return round((0.75 * cfit + 0.25 * ffit) * 100, 2)


def final_score(candidate, reel_metrics, filters, cfg, soft_exclude_hits=0):
    weights = cfg.get("weights", {})
    desired = cfg.get("desired_categories", [])

    visual = candidate.visual_similarity if candidate.visual_similarity is not None else 0.0
    content = candidate.content_similarity if candidate.content_similarity is not None else 0.0
    cfit = category_fit(candidate, desired, soft_exclude_hits)
    ffit = follower_fit(candidate.followers, filters["min_followers"], filters["max_followers"])

    # Clamp performance components to stable 0..1 ranges.
    ad_perf = min(max(reel_metrics.get("ad_view_ratio", 0.0), 0.0), 1.0)
    eng = min(max(reel_metrics.get("ad_engagement_rate", 0.0) / 0.08, 0.0), 1.0)

    score = (
        visual * weights.get("visual_similarity", 0.30)
        + content * weights.get("content_similarity", 0.20)
        + cfit * weights.get("category_fit", 0.10)
        + ad_perf * weights.get("ad_performance", 0.20)
        + eng * weights.get("engagement", 0.15)
        + ffit * weights.get("follower_fit", 0.05)
    )
    return round(score * 100, 2)
