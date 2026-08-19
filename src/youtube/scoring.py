def subscriber_fit(subscribers, minimum, maximum):
    if subscribers is None:
        return 0.0
    if subscribers < minimum or subscribers > maximum:
        return 0.0
    return 1.0


def final_score(channel, metrics, filters, weights):
    doctor_fit = channel.category_scores.get("doctor", 0.0)

    # Related medical/nutrition categories contribute to doctor relevance,
    # but cannot fully replace an explicit doctor signal.
    doctor_fit = min(
        1.0,
        doctor_fit
        + 0.20 * channel.category_scores.get("internal_medicine", 0.0)
        + 0.10 * channel.category_scores.get("health", 0.0)
    )

    ad_perf = min(metrics.get("ad_to_organic_ratio", 0.0), 1.0)
    engagement = min(
        metrics.get("avg_engagement_on_views", 0.0) / 0.08,
        1.0
    )
    sub_fit = subscriber_fit(
        channel.subscribers,
        filters["min_subscribers"],
        filters["max_subscribers"],
    )

    score = (
        doctor_fit * weights["doctor_fit"]
        + channel.seed_similarity * weights["seed_similarity"]
        + ad_perf * weights["ad_performance"]
        + engagement * weights["engagement"]
        + sub_fit * weights["subscriber_fit"]
    )
    return round(score * 100, 2)
