def build_text(bio: str, captions: list[str]) -> str:
    return " ".join([bio or ""] + [x or "" for x in captions]).lower()


def category_scores(text: str, keyword_map: dict):
    scores = {}

    for category, keywords in keyword_map.items():
        if not keywords:
            scores[category] = 0.0
            continue

        hits = sum(1 for kw in keywords if kw.lower() in text)
        scores[category] = round(hits / len(keywords), 4)

    return scores
