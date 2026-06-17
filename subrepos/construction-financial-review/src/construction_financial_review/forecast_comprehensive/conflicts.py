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

    # dormant / closed-code suppression disclosure + defensive review classes
    dormant = entry.get("dormant")
    if dormant:
        st = dormant.get("dormant_status")
        actual = _d(entry.get("actual_cost_to_date"))
        positive_forecast = integrated_final is not None and integrated_final > actual + Decimal("0.01")
        if dormant.get("suppression_applied"):
            cls = "closed_code_forecast_suppressed" if st == "closed_do_not_use" else "dormant_code_model_forecast_suppressed"
            out.append(_conflict(project_key, key, cost_code, cls, "low",
                                 dormant.get("suppression_reason"),
                                 ["dormant_code", "forecast_intelligence"]))
        if dormant.get("operator_control_override"):
            out.append(_conflict(project_key, key, cost_code, "dormant_code_overridden_by_operator_control",
                                 "medium", "dormancy overridden by a value-asserting accepted operator "
                                 "model control (positive remaining)", ["dormant_code", "operator_model_control"]))
        if dormant.get("closure_phrase_detected") and not dormant.get("suppression_applied") \
                and not dormant.get("operator_control_override") and not dormant.get("remaining_evidence") \
                and positive_forecast:
            out.append(_conflict(project_key, key, cost_code,
                                 "closed_code_has_positive_forecast_without_operator_acceptance", "high",
                                 "CLOSED-marked code carries positive future forecast without affirmative "
                                 "remaining evidence or an accepted operator control",
                                 ["dormant_code", "forecast_intelligence"]))
        elif st in ("dormant_no_recent_cost", "inactive_no_remaining_evidence") \
                and not dormant.get("suppression_applied") and not dormant.get("remaining_evidence") \
                and positive_forecast:
            out.append(_conflict(project_key, key, cost_code,
                                 "dormant_code_has_positive_forecast_without_remaining_evidence", "high",
                                 "dormant code carries positive future forecast without affirmative "
                                 "remaining evidence", ["dormant_code", "forecast_intelligence"]))
        if _d(dormant.get("open_commitment_remaining")) > Decimal("0.01"):
            out.append(_conflict(project_key, key, cost_code, "dormant_code_has_open_commitment_remaining",
                                 "medium", f"open commitment remaining {dormant.get('open_commitment_remaining')} "
                                 "keeps an otherwise-idle code forecastable", ["dormant_code", "commitment"]))
        if dormant.get("schedule_remaining_evidence"):
            out.append(_conflict(project_key, key, cost_code, "dormant_code_has_future_schedule_evidence",
                                 "medium", "mapped future schedule work keeps an otherwise-idle code "
                                 "forecastable", ["dormant_code", "schedule_remaining_work"]))
        if dormant.get("non_staffing_suppression_candidate"):
            out.append(_conflict(project_key, key, cost_code, "non_staffing_recent_zero_run_advisory",
                                 "low", "non-staffing code has a recent zero-cost run; advisory only "
                                 "(recent-zero-run suppression is staffing/GC-only this slice)",
                                 ["dormant_code", "cost_entry_trend"]))

    # operator forecast-model control disclosure: a value-changing control overrides the model forecast
    # (and a binding not_to_exceed is disclosed as an operator constraint, never a silent cap); a
    # value-changing control with no prior accepted probability row runs on a provisional assessment.
    mdec = entry.get("model_control")
    if mdec:
        if mdec.get("changes_deterministic_final"):
            out.append(_conflict(
                project_key, key, cost_code, "operator_model_overrides_model_forecast", "medium",
                f"operator model control '{mdec['control_id']}' "
                f"({mdec['value_constraint_policy']}/{mdec['model_type']}) sets final="
                f"{mdec['controlled_final_cost']} vs model evidence",
                ["operator_model_control", "forecast_intelligence"]))
            if mdec["value_constraint_policy"] == "not_to_exceed_reference" and mdec.get("constraint_applied"):
                out.append(_conflict(
                    project_key, key, cost_code, "operator_not_to_exceed_constraint_applied", "medium",
                    "operator not_to_exceed constraint lowered the model result (disclosed, not a cap)",
                    ["operator_model_control", "budget_reference"]))
            if not pfin:
                out.append(_conflict(
                    project_key, key, cost_code, "operator_model_missing_prior_probability_row", "low",
                    "controlled final has no prior accepted probability row; probability is a provisional "
                    "assessment (deterministic run unaffected)",
                    ["operator_model_control", "forecast_probability"]))

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

    out.extend(_operator_control_conflicts(project_key, key, cost_code, entry))
    # operator staffing-plan conflicts are emitted by the staffing-plan package in the comprehensive
    # conflict-row schema; surface them here so they enter the integrated conflict register + review queue.
    out.extend(entry.get("staffing_plan_conflicts") or [])
    return out


def _operator_control_conflicts(project_key, key, cost_code, entry) -> list:
    """Conflicts between explicit operator controls and the model forecast / schedule / actuals."""
    out = []
    decision = entry.get("operator_control")
    apps = entry.get("operator_control_apps") or []
    sched = entry.get("sched") or {}

    if decision and (decision.get("timing_applied") or decision.get("dollar_applied")):
        out.append(_conflict(project_key, key, cost_code, "operator_control_conflicts_with_model_forecast",
                             "medium", f"operator control {decision.get('control_id')} overrides the model "
                             f"forecast ({decision.get('disposition')})",
                             ["operator_forecast_control", "forecast_intelligence"]))
        if decision.get("timing_applied") and sched.get("influences_code_estimate"):
            out.append(_conflict(project_key, key, cost_code,
                                 "operator_stop_date_conflicts_with_schedule_remaining_work", "high",
                                 "operator stop-date applied but schedule remaining-work still influences "
                                 f"this code (status={sched.get('schedule_remaining_work_status')})",
                                 ["operator_forecast_control", "schedule_remaining_work"]))

    for a in apps:
        if a.get("disposition") in ("rejected_final_below_actuals", "rejected_remaining_below_zero"):
            out.append(_conflict(project_key, key, cost_code,
                                 "operator_remaining_allowance_below_actuals", "high",
                                 f"accepted operator amount for {a.get('control_id')} is below actual cost "
                                 "to date; rejected (floor preserved)",
                                 ["operator_forecast_control", "actual_cost_truth"]))
        elif a.get("disposition") == "pending_not_applied":
            out.append(_conflict(project_key, key, cost_code, "operator_control_pending_not_applied",
                                 "medium", f"pending operator control {a.get('control_id')} exists but is "
                                 "not applied (awaiting human acceptance)",
                                 ["operator_forecast_control"]))
    return out
