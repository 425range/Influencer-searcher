def follower_fit(followers, minimum, maximum):
    if followers is None or followers < minimum or followers > maximum:
        return 0.0

    # Broadly reward accounts inside the requested band.
    return 1.0


def final_score(candidate, metrics, filters, weights):
    desired_category = (
        candidate.category_scores.get("fitness", 0)
        + candidate.category_scores.get("selfcare", 0)
        + candidate.category_scores.get("office", 0)
        + candidate.category_scores.get("lifestyle", 0)
    ) / 4

    beauty_penalty = candidate.category_scores.get("beauty", 0) * 0.20
    category_fit = max(0.0, min(1.0, desired_category - beauty_penalty))

    ad_perf = min(metrics.get("ad_to_organic_ratio", 0), 1.0)
    engagement = min(metrics.get("engagement_on_views", 0) / 0.08, 1.0)

    ffit = follower_fit(
        candidate.followers,
        filters["min_followers"],
        filters["max_followers"],
    )

    score = (
        candidate.seed_similarity * weights["seed_similarity"]
        + category_fit * weights["category_fit"]
        + ad_perf * weights["ad_performance"]
        + engagement * weights["engagement"]
        + ffit * weights["follower_fit"]
    )

    return round(score * 100, 2)
