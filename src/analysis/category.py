import re
from collections import defaultdict


def category_scores(text: str, category_keywords: dict) -> dict[str, float]:
    text = (text or "").lower()
    scores = {}

    for category, keywords in category_keywords.items():
        if not keywords:
            scores[category] = 0.0
            continue

        hits = 0
        for kw in keywords:
            if kw.lower() in text:
                hits += 1

        scores[category] = round(hits / len(keywords), 4)

    return scores


def combined_profile_text(bio: str, captions: list[str]) -> str:
    return " ".join([bio or ""] + [c or "" for c in captions])
