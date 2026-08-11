def seed_similarity(candidate, seed_profile_texts: list[str]):
    """
    Lightweight v0.2 similarity:
    - Instagram relatedProfiles is the strongest signal.
    - textual overlap adds a small refinement.

    This deliberately avoids embeddings/LLM for the first PoC.
    """
    base = 0.75 if candidate.source == "seed_related" else 0.15

    candidate_words = {
        w for w in (candidate.bio or "").lower().replace("#", " ").split()
        if len(w) >= 2
    }

    if not candidate_words or not seed_profile_texts:
        return base

    best = 0.0
    for text in seed_profile_texts:
        seed_words = {
            w for w in (text or "").lower().replace("#", " ").split()
            if len(w) >= 2
        }
        if not seed_words:
            continue

        overlap = len(candidate_words & seed_words)
        union = len(candidate_words | seed_words)
        best = max(best, overlap / union if union else 0.0)

    return round(min(1.0, base + 0.25 * best), 4)
