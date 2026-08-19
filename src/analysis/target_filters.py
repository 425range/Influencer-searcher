import re


def _hits(text: str, keywords: list[str]) -> list[str]:
    text = (text or "").lower()
    return [kw for kw in keywords if kw and kw.lower() in text]


DEFAULT_GENDER_SIGNALS = {
    "female": {
        "bio": [
            "여성", "여대생", "워킹맘", "엄마", "여자패션", "여자 패션",
            "여자코디", "여자 코디", "female creator", "woman creator",
            "mom creator", "mother", "she/her",
        ],
        "caption": [
            "저는 여자", "저는 여성", "여자인", "여성 직장인", "여자 직장인",
            "여대생", "워킹맘", "엄마입니다", "female creator", "woman creator",
        ],
    },
    "male": {
        "bio": [
            "남성", "남자패션", "남자 패션", "남자코디", "남자 코디",
            "아빠", "male creator", "man creator", "dad creator", "father",
            "he/him",
        ],
        "caption": [
            "저는 남자", "저는 남성", "남자인", "남성 직장인", "남자 직장인",
            "아빠입니다", "남자패션", "남성패션", "male creator", "man creator",
        ],
    },
}


def _signal_hits(text: str, keywords: list[str]) -> list[str]:
    """Conservative literal phrase matching for explicit self-description signals."""
    text = (text or "").lower()
    found = []
    for kw in keywords:
        k = (kw or "").strip().lower()
        if k and k in text and kw not in found:
            found.append(kw)
    return found


def evaluate_gender_target(bio: str, captions: list[str], gender_cfg: dict | None) -> dict:
    """
    Conservative creator-gender target filter based only on explicit text signals.

    It does NOT infer gender from images, names, or appearance.
    Unknown/ambiguous accounts are kept. A candidate is rejected only when the
    opposite target has sufficiently stronger explicit self-description evidence.
    """
    cfg = gender_cfg or {}
    target = str(cfg.get("target", "all") or "all").lower()
    enabled = bool(cfg.get("enabled", target != "all"))

    if not enabled or target == "all":
        return {
            "gender_target": "all",
            "gender_signal": "not_filtered",
            "gender_target_match": True,
            "gender_reject": False,
            "gender_evidence": "",
            "female_score": 0.0,
            "male_score": 0.0,
        }

    if target not in {"female", "male"}:
        return {
            "gender_target": "all",
            "gender_signal": "not_filtered",
            "gender_target_match": True,
            "gender_reject": False,
            "gender_evidence": "",
            "female_score": 0.0,
            "male_score": 0.0,
        }

    bio_weight = float(cfg.get("bio_weight", 3.0))
    caption_weight = float(cfg.get("caption_weight", 1.0))
    reject_threshold = float(cfg.get("reject_threshold", 3.0))
    margin = float(cfg.get("opposite_margin", 2.0))

    custom = cfg.get("signals", {}) or {}
    signals = {
        side: {
            "bio": list((custom.get(side, {}) or {}).get("bio", DEFAULT_GENDER_SIGNALS[side]["bio"])),
            "caption": list((custom.get(side, {}) or {}).get("caption", DEFAULT_GENDER_SIGNALS[side]["caption"])),
        }
        for side in ("female", "male")
    }

    bio_hits = {}
    caption_hits = {}
    caption_text = "\n".join(captions or [])
    scores = {}

    for side in ("female", "male"):
        bio_hits[side] = _signal_hits(bio, signals[side]["bio"])
        caption_hits[side] = _signal_hits(caption_text, signals[side]["caption"])
        # Caption evidence is deliberately capped so repeated mentions do not dominate.
        scores[side] = bio_weight * len(bio_hits[side]) + caption_weight * min(len(caption_hits[side]), 2)

    female_score = scores["female"]
    male_score = scores["male"]

    if female_score == 0 and male_score == 0:
        signal = "unknown"
    elif abs(female_score - male_score) < margin:
        signal = "ambiguous"
    elif female_score > male_score:
        signal = "female_explicit"
    else:
        signal = "male_explicit"

    opposite = "male" if target == "female" else "female"
    target_score = scores[target]
    opposite_score = scores[opposite]

    reject = (
        opposite_score >= reject_threshold
        and opposite_score >= target_score + margin
    )

    evidence_parts = []
    if bio_hits["female"]:
        evidence_parts.append("female bio=" + ",".join(bio_hits["female"]))
    if bio_hits["male"]:
        evidence_parts.append("male bio=" + ",".join(bio_hits["male"]))
    if caption_hits["female"]:
        evidence_parts.append("female caption=" + ",".join(caption_hits["female"]))
    if caption_hits["male"]:
        evidence_parts.append("male caption=" + ",".join(caption_hits["male"]))

    return {
        "gender_target": target,
        "gender_signal": signal,
        "gender_target_match": not reject,
        "gender_reject": reject,
        "gender_evidence": " | ".join(evidence_parts),
        "female_score": female_score,
        "male_score": male_score,
    }


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
