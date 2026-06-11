"""Phase 10 V51 — deterministic, aggregate, bounded feedback calibration.

Turns the raw-free V50 feedback read model (acceptance/rejection/disposition counts by family) into
a small per-family calibration that nudges a candidate's *feedback score* up or down. The effect is
deliberately weak and conservative:

* **Threshold** — a family is calibrated only when it has at least ``MIN_FEEDBACK_SAMPLES`` reviewed
  outcomes; below that the family stays neutral (no calibration from a tiny sample).
* **Clamp** — the adjustment is clamped to ``±MAX_CALIBRATION_ADJUSTMENT`` on the normalized 0..1
  scale, so calibration can never dominate the deterministic base score.
* **No negative transfer** — a candidate is scored only from *its own* family's outcomes; a
  different family's (or project's) rejections never punish it.
* **Raw-free** — only counts, rates, and family codes are read; never raw text, bodies, or refs.

Calibrated scores are reported on the 0..100 scale used by the ranking blend; neutral is 50.
"""

from __future__ import annotations

from typing import Any, Optional

#: Minimum reviewed outcomes in a family before any calibration applies (conservative).
MIN_FEEDBACK_SAMPLES = 5
#: Maximum calibration nudge on the normalized 0..1 scale (±0.10 → ±10 points on 0..100).
MAX_CALIBRATION_ADJUSTMENT = 0.10
#: Neutral feedback score (no signal) on the 0..100 scale.
NEUTRAL_FEEDBACK_SCORE = 50.0

CALIBRATION_VERSION = "feedback-cal-v1"

_REVIEWED_STATES = ("accepted", "rejected", "snoozed", "merged", "suppressed", "closed")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def build_family_calibration(feedback_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per-family calibration metadata derived from the feedback read model (raw-free).

    For each family: the reviewed sample size, its acceptance rate, whether the threshold was met,
    and the clamped adjustment on the normalized 0..1 scale. A family below the sample threshold is
    reported with ``applied=False`` and a zero adjustment.
    """
    by_family: dict[str, int] = dict(feedback_summary.get("by_family") or {})
    acceptance_rate_by_family: dict[str, float] = dict(
        feedback_summary.get("acceptance_rate_by_family") or {}
    )
    # Reviewed sample size per family is approximated by the family's total surfaced count; the
    # acceptance rate is already computed by the feedback read model over the same denominator.
    out: dict[str, dict[str, Any]] = {}
    for family, total in sorted(by_family.items()):
        rate = float(acceptance_rate_by_family.get(family, 0.0))
        applied = total >= MIN_FEEDBACK_SAMPLES
        # Map acceptance rate [0,1] (neutral 0.5) onto a clamped ±MAX adjustment.
        raw_adjustment = (rate - 0.5) * 2.0 * MAX_CALIBRATION_ADJUSTMENT
        adjustment = (
            _clamp(raw_adjustment, -MAX_CALIBRATION_ADJUSTMENT, MAX_CALIBRATION_ADJUSTMENT)
            if applied
            else 0.0
        )
        out[family] = {
            "sample_size": int(total),
            "acceptance_rate": round(rate, 4),
            "threshold_met": applied,
            "applied": applied and adjustment != 0.0,
            "adjustment": round(adjustment, 4),
        }
    return out


def build_calibration(feedback_summary: dict[str, Any]) -> dict[str, Any]:
    """Build the full raw-free calibration metadata block for a brief date."""
    families = build_family_calibration(feedback_summary)
    return {
        "calibration_version": CALIBRATION_VERSION,
        "min_feedback_samples": MIN_FEEDBACK_SAMPLES,
        "max_calibration_adjustment": MAX_CALIBRATION_ADJUSTMENT,
        "families": families,
        "applied_family_count": sum(1 for f in families.values() if f["applied"]),
        "no_negative_transfer": True,
    }


def feedback_score_for_family(family: Optional[str], calibration: dict[str, Any]) -> float:
    """Return the calibrated feedback score (0..100) for a candidate in ``family``.

    Neutral (50) when the family has no calibration; otherwise neutral plus the family's clamped
    adjustment. A candidate is never scored from another family's outcomes (no negative transfer).
    """
    if not family:
        return NEUTRAL_FEEDBACK_SCORE
    fam = calibration.get("families", {}).get(family)
    if not fam or not fam.get("applied"):
        return NEUTRAL_FEEDBACK_SCORE
    normalized = _clamp(0.5 + float(fam["adjustment"]), 0.0, 1.0)
    return round(normalized * 100.0, 4)
