"""Classify useful evidence conflicts per budget code (not just presence)."""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, materiality

ZERO = Decimal("0")


def _d(x):
    v = dec(x)
    return v if v is not None else ZERO


def _conflict(project_key, key, cost_code, cls, severity, detail, families):
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("conflict_class", cls), ("severity", severity), ("detail", detail),
        ("families_involved", families), ("requires_human_acceptance", True),
    ])


def build(project_key, key, entry, sc, integrated_final: Decimal) -> list:
    cost_code = key.split(".")[1] if "." in key else None
    out = []
    sched = entry["sched"]
    mconf, pfin, freq = entry["monthly_conf"], entry["prob_final"], entry["freq"]
    ss = (mconf or {}).get("source_shares") or {}

    if sc["contradicted"]:
        out.append(_conflict(project_key, key, cost_code, "actuals_contradict_history", "high",
                             f"validation={sc['validation_class']}; history final-cost weight collapsed",
                             ["actual_cost_truth", "history_informed_final_cost"]))

    if sched.get("influences_code_estimate") and mconf and \
            mconf.get("monthly_forecast_basis") not in ("schedule_phasing", "combined"):
        out.append(_conflict(project_key, key, cost_code, "schedule_contradicts_monthly_shape", "medium",
                             f"schedule influences code but monthly basis={mconf.get('monthly_forecast_basis')}",
                             ["schedule_remaining_work", "forecast_monthly"]))

    if _d(ss.get("subcontractor_invoice_weight")) >= Decimal("0.4") and \
            _d(ss.get("cost_entries_weight")) >= Decimal("0.4"):
        out.append(_conflict(project_key, key, cost_code, "invoice_trend_contradicts_cost_entry_trend",
                             "low", "invoice and cost-entry trends both strongly drive monthly timing",
                             ["subcontractor_pay_application", "cost_entry_trend"]))

    if pfin and _d(pfin.get("prob_exceeds_recommended_final_cost")) >= Decimal("0.5") and \
            (entry["conf"].get("confidence_band") in ("high", "very_high")):
        out.append(_conflict(project_key, key, cost_code, "probability_risk_contradicts_confidence_band",
                             "high", "high calibrated confidence but >50% probability over recommended final",
                             ["forecast_probability", "forecast_accuracy"]))

    if freq and freq.get("cadence_change_detected"):
        out.append(_conflict(project_key, key, cost_code, "frequency_cadence_contradicts_recent_actuals",
                             "low", freq.get("cadence_change_basis"),
                             ["cost_frequency_cadence", "actual_cost_truth"]))

    ov = entry["owner_pay_app"].get("latest_current_value")
    sv = entry["sub_pay_app"].get("latest_total_completed_and_stored_to_date_sum")
    if ov is not None and sv is not None:
        _, _, mat = materiality(D(ov), D(sv))
        if mat:
            out.append(_conflict(project_key, key, cost_code, "owner_vs_subcontractor_pay_app_mismatch",
                                 "medium", f"owner pay app {ov} vs subcontractor {sv} differ materially",
                                 ["owner_pay_application", "subcontractor_pay_application"]))

    projected = entry["projected_costs"]
    if projected is not None:
        _, _, mat = materiality(integrated_final, D(projected))
        if mat:
            out.append(_conflict(project_key, key, cost_code,
                                 "current_projected_diverges_from_integrated_forecast", "high",
                                 f"integrated final {integrated_final} vs current projected {projected}",
                                 ["current_projected_cost", "forecast_intelligence"]))
    return out
