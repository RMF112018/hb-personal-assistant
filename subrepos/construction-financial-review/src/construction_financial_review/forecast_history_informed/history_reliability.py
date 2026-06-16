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
ACTIVITY_MATERIAL = Decimal("25000")   # CostEntries burn/window threshold for "strong" actual activity

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


def _cost_entry_activity_support(validation: dict) -> Decimal:
    """Graded CostEntries monthly actual-cost support (the PRIMARY actual-evidence signal).

    Sourced from the validation row's CostEntries-derived recent burn + post-snapshot window activity
    (accounting truth by canonical budget code). Strong = material recent burn; weak = older/lighter
    activity; absent = no booked cost. Never derived from historical forecast or invoice evidence.
    """
    burn6 = _d(validation.get("recent_6mo_burn")).copy_abs()
    burn12 = _d(validation.get("recent_12mo_burn")).copy_abs()
    window = _d(validation.get("cost_entries_actual_cost_in_window")).copy_abs()
    if burn6 >= ACTIVITY_MATERIAL:
        return ONE                       # strong: sustained recent CostEntries activity
    if burn12 >= ACTIVITY_MATERIAL or window >= ACTIVITY_MATERIAL:
        return Decimal("0.5")            # weak: material activity, but not recent-sustained
    if burn12 > ZERO or window > ZERO:
        return Decimal("0.25")           # trace: minor booked cost
    return ZERO                          # absent: no CostEntries actuals


def build_reliability(signal: dict, validation: dict, intel: dict, key, reference_month,
                      half_life_months, monthly_source_row, project_key: str) -> OrderedDict:
    persistence = _d(signal.get("historical_signal_strength"))
    stability = _d(signal.get("forecast_stability_score"))
    recency = _recency_score(signal.get("latest_historical_forecast_month"),
                             reference_month, half_life_months)
    vclass = validation.get("validation_class")
    actual_validation = VALIDATION_SCORE.get(vclass, Decimal("0.40"))
    contradiction = _d(validation.get("actual_trend_override_score"))

    sched = (intel.get("schedule") or {}).get(key) if intel else None
    schedule_support = _d(sched.get("schedule_confidence")) if sched else ZERO

    # tiered actual-evidence support: CostEntries activity (primary) > true subcontractor-invoice
    # support (secondary, accepted-monthly source share) > months-of-completed-actuals density
    # (tertiary fallback proxy). months_of_completed_actuals is NEVER labeled invoice support.
    cost_entry_activity_support = _cost_entry_activity_support(validation)
    inv_shares = (monthly_source_row or {}).get("source_shares") or {}
    subcontractor_invoice_support = _d(inv_shares.get("subcontractor_invoice_weight")).max(ZERO).min(ONE)
    trend = (intel.get("trend") or {}).get(key) if intel else None
    actual_history_density_support = ONE if (trend and trend.get("months_of_completed_actuals")) else ZERO
    actual_evidence_support = (cost_entry_activity_support * Decimal("0.60")
                               + subcontractor_invoice_support * Decimal("0.30")
                               + actual_history_density_support * Decimal("0.10"))

    # weighted blend, then collapse by contradiction (actuals dominate)
    blended = (persistence * Decimal("0.20") + recency * Decimal("0.20")
               + stability * Decimal("0.15") + actual_validation * Decimal("0.30")
               + schedule_support * Decimal("0.10") + actual_evidence_support * Decimal("0.05"))
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
        ("cost_entry_activity_support_score", _q4(cost_entry_activity_support)),
        ("subcontractor_invoice_support_score", _q4(subcontractor_invoice_support)),
        ("actual_history_density_support_score", _q4(actual_history_density_support)),
        ("actual_evidence_support_score", _q4(actual_evidence_support)),
        ("overall_history_reliability_score", _q4(overall)),
        ("reliability_band", band),
        ("reason_codes", reasons),
        ("requires_human_acceptance", True),
    ])
