"""Blend historical-signal + actual-validation + supporting evidence into a reliability score.

Reliability says how much weight a prior forecast assumption deserves. Persistent, recent, stable
history that CostEntries actuals confirm is reliable; history contradicted by recent escalation is not.
Actuals always dominate: contradiction collapses the score regardless of how persistent the history is.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

ZERO = Decimal("0")
ONE = Decimal("1")

VALIDATION_SCORE = {
    "validated_zero_inactive": Decimal("0.90"),
    "validated_aligned": Decimal("0.85"),
    "history_overstated_remaining": Decimal("0.45"),
    "inconclusive": Decimal("0.40"),
    "inconclusive_zero": Decimal("0.40"),
    "actuals_exceed_history": Decimal("0.25"),
    "contradicted_unexpected_actuals": Decimal("0.10"),
    "contradicted_escalation": Decimal("0.05"),
    "insufficient_actuals_no_unique_mapping": Decimal("0.20"),
}

BANDS = (
    (Decimal("0.80"), "very_high"), (Decimal("0.60"), "high"),
    (Decimal("0.40"), "medium"), (Decimal("0.20"), "low"), (ZERO, "very_low"),
)


def _q4(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))


def _d(x, default=ZERO):
    try:
        return Decimal(str(x))
    except Exception:
        return default


def _recency_score(latest_snapshot, reference_month, half_life_months) -> Decimal:
    """0.5 ** (months_gap / half_life): newest snapshots score ~1, stale ones decay."""
    if not latest_snapshot or not reference_month:
        return ZERO
    gap = _month_gap(latest_snapshot, reference_month)
    if gap <= 0:
        return ONE
    hl = Decimal(str(half_life_months or 6))
    return Decimal("0.5") ** (Decimal(gap) / hl)


def _month_gap(a: str, b: str) -> int:
    ya, ma = int(a[:4]), int(a[5:7])
    yb, mb = int(b[:4]), int(b[5:7])
    return (yb - ya) * 12 + (mb - ma)


def build_reliability(signal: dict, validation: dict, intel: dict, key, reference_month,
                      half_life_months, project_key: str) -> OrderedDict:
    persistence = _d(signal.get("historical_signal_strength"))
    stability = _d(signal.get("forecast_stability_score"))
    recency = _recency_score(signal.get("latest_historical_forecast_month"),
                             reference_month, half_life_months)
    vclass = validation.get("validation_class")
    actual_validation = VALIDATION_SCORE.get(vclass, Decimal("0.40"))
    contradiction = _d(validation.get("actual_trend_override_score"))

    sched = (intel.get("schedule") or {}).get(key) if intel else None
    schedule_support = _d(sched.get("schedule_confidence")) if sched else ZERO
    trend = (intel.get("trend") or {}).get(key) if intel else None
    invoice_support = ONE if (trend and trend.get("months_of_completed_actuals")) else ZERO

    # weighted blend, then collapse by contradiction (actuals dominate)
    blended = (persistence * Decimal("0.20") + recency * Decimal("0.20")
               + stability * Decimal("0.15") + actual_validation * Decimal("0.30")
               + schedule_support * Decimal("0.10") + invoice_support * Decimal("0.05"))
    overall = (blended * (ONE - contradiction)).max(ZERO).min(ONE)

    reasons = []
    if vclass and vclass.startswith("validated"):
        reasons.append("actuals_confirm_history")
    if vclass and vclass.startswith("contradicted"):
        reasons.append("actuals_contradict_history")
    if recency < Decimal("0.25"):
        reasons.append("stale_history")
    if stability >= Decimal("0.75"):
        reasons.append("stable_forecast_history")
    if signal.get("duplicate_cost_code_warning"):
        reasons.append("duplicate_cost_code_lineage")
    if signal.get("mapping_status") != "cost_code_unique_budget_match":
        reasons.append("non_unique_mapping")

    band = next(name for thr, name in BANDS if overall >= thr)
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", signal.get("cost_code")),
        ("history_persistence_score", _q4(persistence)),
        ("history_recency_score", _q4(recency)),
        ("history_stability_score", _q4(stability)),
        ("history_actual_validation_score", _q4(actual_validation)),
        ("actual_contradiction_score", _q4(contradiction)),
        ("schedule_support_score", _q4(schedule_support)),
        ("invoice_support_score", _q4(invoice_support)),
        ("overall_history_reliability_score", _q4(overall)),
        ("reliability_band", band),
        ("reason_codes", reasons),
        ("requires_human_acceptance", True),
    ])
