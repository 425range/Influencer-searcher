from __future__ import annotations


def _clamp01(x):
    return max(0.0, min(1.0, float(x)))


def evaluate_creator_target(candidate, cfg: dict | None) -> dict:
    """
    Composite target gate.

    This is NOT a face-gender classifier. It uses:
      - explicit Bio/Caption target mismatch handled earlier
      - positive Reference visual similarity
      - visual consistency across recent posts
      - topic-profile similarity
      - optional Negative Reference contrast

    It therefore asks "does this account behave/look like the marketer's
    selected creator set?" instead of "what gender is this person?"
    """
    cfg = cfg or {}
    enabled = bool(cfg.get("enabled", True))
    if not enabled:
        return {
            "creator_target_fit": None,
            "creator_target_gate": "disabled",
            "creator_target_reject": False,
            "creator_target_reason": "",
        }

    min_visual_reference = float(cfg.get("min_visual_reference", 0.89))
    min_visual_median = float(cfg.get("min_visual_median", 0.82))
    min_topic_similarity = float(cfg.get("min_topic_similarity", 0.50))
    min_target_fit = float(cfg.get("min_target_fit", 0.52))
    negative_margin_reject = float(cfg.get("negative_margin_reject", -0.02))
    reject_low_visual_pair = bool(cfg.get("reject_low_visual_pair", True))

    visual_ref = candidate.visual_reference_similarity
    visual_med = candidate.visual_post_median_similarity
    topic = candidate.topic_similarity
    visual_margin = candidate.visual_target_margin
    topic_margin = candidate.topic_target_margin

    # Convert absolute visual similarities into a more interpretable fit scale
    # around the model-specific floor used by this project.
    parts = []
    if visual_ref is not None:
        parts.append((_clamp01((visual_ref - 0.75) / 0.25), 0.45))
    if visual_med is not None:
        parts.append((_clamp01((visual_med - 0.65) / 0.35), 0.25))
    if topic is not None:
        parts.append((_clamp01(topic), 0.30))

    denom = sum(w for _, w in parts)
    fit = sum(v * w for v, w in parts) / denom if denom else None

    reasons = []
    reject = False

    # Rule 1: both account-level and post-level positive visual fit are weak.
    if (
        reject_low_visual_pair
        and visual_ref is not None
        and visual_med is not None
        and visual_ref < min_visual_reference
        and visual_med < min_visual_median
    ):
        reject = True
        reasons.append(
            f"low_positive_visual(ref={visual_ref:.3f}<"
            f"{min_visual_reference:.3f},median={visual_med:.3f}<"
            f"{min_visual_median:.3f})"
        )

    # Rule 2: when negative references exist, reject only if a negative set is
    # clearly closer. This is marketer-provided supervision, not identity inference.
    negative_evidence = []
    if visual_margin is not None:
        negative_evidence.append(visual_margin)
    if topic_margin is not None:
        negative_evidence.append(topic_margin)

    if negative_evidence and max(negative_evidence) < negative_margin_reject:
        reject = True
        reasons.append(
            "closer_to_negative_reference:"
            + ",".join(f"{x:.3f}" for x in negative_evidence)
        )

    # Rule 3: low topic + weak overall target fit is a secondary gate.
    if (
        not reject
        and fit is not None
        and fit < min_target_fit
        and (topic is None or topic < min_topic_similarity)
    ):
        reject = True
        reasons.append(
            f"low_creator_target_fit({fit:.3f}<{min_target_fit:.3f})"
        )

    gate = "reject" if reject else ("pass" if fit is not None else "insufficient_data")
    return {
        "creator_target_fit": fit,
        "creator_target_gate": gate,
        "creator_target_reject": reject,
        "creator_target_reason": " | ".join(reasons),
    }
