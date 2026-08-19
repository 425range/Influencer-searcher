def _hits(text: str, keywords: list[str]) -> list[str]:
    text = (text or "").lower()
    return [kw for kw in keywords if kw and kw.lower() in text]


def apply_targeting(text: str, targeting: dict) -> dict:
    include = _hits(text, targeting.get("include_keywords", []))
    hard_exclude = _hits(text, targeting.get("hard_exclude_keywords", []))
    soft_exclude = _hits(text, targeting.get("soft_exclude_keywords", []))

    return {
        "include_hits": include,
        "hard_exclude_hits": hard_exclude,
        "soft_exclude_hits": soft_exclude,
        "hard_reject": bool(hard_exclude),
    }
