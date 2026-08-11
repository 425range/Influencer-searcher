def _follower_fit(followers, min_followers, max_followers):
    if followers is None:
        return 0.0
    if followers < min_followers or followers > max_followers:
        return 0.0

    midpoint = (min_followers + max_followers) / 2
    half = max((max_followers - min_followers) / 2, 1)
    distance = abs(followers - midpoint) / half
    return max(0.0, 1.0 - 0.4 * distance)


def score_candidate(
    category_scores: dict,
    metrics: dict,
    followers,
    filters: dict,
    weights: dict,
):
    # For this MVP, category fit prioritizes selfcare / fitness / office,
    # and mildly penalizes beauty-heavy profiles.
    desired = (
        category_scores.get("selfcare", 0)
        + category_scores.get("fitness", 0)
        + category_scores.get("office", 0)
    ) / 3

    beauty_penalty = category_scores.get("beauty", 0) * 0.25
    category_fit = max(0.0, min(1.0, desired - beauty_penalty))

    ad_ratio = min(metrics.get("ad_to_organic_view_ratio", 0.0), 1.0)
    engagement = min(metrics.get("engagement_on_views", 0.0) / 0.08, 1.0)
    follower_fit = _follower_fit(
        followers,
        filters["min_followers"],
        filters["max_followers"],
    )

    final = (
        category_fit * weights.get("category_fit", 0.35)
        + ad_ratio * weights.get("ad_performance", 0.30)
        + engagement * weights.get("engagement", 0.20)
        + follower_fit * weights.get("follower_fit", 0.15)
    )

    return round(final * 100, 2)
