"""Load accepted package rows and normalize them into a per-budget-code evidence registry.

Reads OUTPUT rows only (no recompute, no mutation). History / cost-frequency rows are joined on the
canonical budget_code_key; rows with no canonical key are NOT invented into the universe (they are
surfaced by the conflict/lineage register). Returns (evidence_items, per_code) where per_code carries
the consolidated raw rows each consumer needs.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from ..common.io import read_json, read_jsonl
from . import evidence_schema as es


def _by_key(path: Path) -> dict:
    if not path or not path.exists():
        return {}
    return {r["budget_code_key"]: r for r in read_jsonl(path) if r.get("budget_code_key")}


def _unmapped(path: Path) -> list:
    if not path or not path.exists():
        return []
    return [r for r in read_jsonl(path) if not r.get("budget_code_key")]


def load_sources(discovery: OrderedDict) -> dict:
    """Load the relevant per-code maps from each discovered package."""
    def p(ptype):
        d = discovery.get(ptype) or {}
        return Path(d["path"]) if d.get("present") else None

    ctx, intel = p("context"), p("intelligence")
    monthly, prob = p("monthly"), p("probability")
    hist, freq = p("history_informed"), p("cost_frequency")
    staffing = p("staffing_plan")

    src = {
        "context_by": _by_key(ctx / "summaries" / "budget_code_forecast_context.jsonl") if ctx else {},
        "rec_by": _by_key(intel / "forecast_recommendations_by_budget_code.jsonl") if intel else {},
        "dormant_by": _by_key(intel / "dormant_code_status_by_budget_code.jsonl") if intel else {},
        "trend_by": _by_key(intel / "trend_evidence_by_budget_code.jsonl") if intel else {},
        "sched_by": _by_key(intel / "schedule_forecast_evidence_by_budget_code.jsonl") if intel else {},
        "conf_by": _by_key(intel / "forecast_confidence_by_budget_code.jsonl") if intel else {},
        "monthly_conf_by": _by_key(monthly / "monthly_forecast_confidence_by_budget_code.jsonl") if monthly else {},
        "monthly_dist_by": _by_key(monthly / "remaining_work_monthly_distribution_by_budget_code.jsonl") if monthly else {},
        "prob_final_by": _by_key(prob / "probabilistic_final_cost_by_budget_code.jsonl") if prob else {},
        "prob_overrun_by": _by_key(prob / "code_overrun_probabilities.jsonl") if prob else {},
        "prob_sim_by": _by_key(prob / "simulation_inputs_by_budget_code.jsonl") if prob else {},
        "hist_adj_by": _by_key(hist / "history_informed_forecast_adjustment_by_budget_code.jsonl") if hist else {},
        "hist_rel_by": _by_key(hist / "historical_assumption_reliability_by_budget_code.jsonl") if hist else {},
        "hist_val_by": _by_key(hist / "historical_vs_actual_validation_by_budget_code.jsonl") if hist else {},
        "hist_mon_by": _by_key(hist / "history_informed_monthly_distribution_by_budget_code.jsonl") if hist else {},
        "hist_prob_by": _by_key(hist / "history_informed_probability_adjustments_by_budget_code.jsonl") if hist else {},
        "hist_unmapped": _unmapped(hist / "history_informed_forecast_adjustment_by_budget_code.jsonl") if hist else [],
        "freq_by": _by_key(freq / "cost_frequency_by_budget_code.jsonl") if freq else {},
        "freq_phasing_by": _by_key(freq / "frequency_adjusted_monthly_phasing_by_budget_code.jsonl") if freq else {},
        "freq_rate_by": _by_key(freq / "internal_staffing_daily_rate_by_budget_code.jsonl") if freq else {},
        "staffing_plan_by": _by_key(staffing / "staffing_plan_summary_by_budget_code.jsonl") if staffing else {},
        "staffing_plan_monthly_by": _by_key(
            staffing / "staffing_plan_monthly_by_budget_code.jsonl") if staffing else {},
        "staffing_plan_conflicts": (list(read_jsonl(staffing / "staffing_plan_conflicts.jsonl"))
                                    if staffing and (staffing / "staffing_plan_conflicts.jsonl").exists()
                                    else []),
        # staffing-basis gating signals: mapping acceptance (keyed by SOURCE cost_code) + validated source
        "staffing_mapping_by_cc": ({r.get("source_cost_code"): r for r in
                                    read_jsonl(staffing / "staffing_plan_mapping_by_cost_code.jsonl")}
                                   if staffing and (staffing / "staffing_plan_mapping_by_cost_code.jsonl").exists()
                                   else {}),
        "staffing_source_validation_passed": (
            bool((read_json(staffing / "staffing_plan_source_inventory.json") or {})
                 .get("source_validation_passed"))
            if staffing and (staffing / "staffing_plan_source_inventory.json").exists() else False),
        "_paths": {"context": ctx, "intelligence": intel, "monthly": monthly, "probability": prob,
                   "history_informed": hist, "cost_frequency": freq, "staffing_plan": staffing},
    }
    return src


def build_registry(canonical_keys, sources: dict, project_key: str, controls_ctx: dict | None = None):
    """Return (evidence_items, per_code). Emit one evidence item per present family per code.

    ``controls_ctx`` (optional) carries operator forecast controls: {"by_key", "apps_by_key",
    "control_file"}. When present, each controlled code gets an ``operator_forecast_control`` evidence
    item and the resolved decision is attached to per_code for the consumers + conflict register.
    """
    items, per_code = [], OrderedDict()
    paths = sources["_paths"]
    controls_ctx = controls_ctx or {}
    ctrl_by_key = controls_ctx.get("by_key") or {}
    ctrl_apps_by_key = controls_ctx.get("apps_by_key") or {}
    ctrl_file = controls_ctx.get("control_file")

    # operator staffing plan (consumed as accepted-package OUTPUT rows; advisory, never auto-applied)
    staffing_plan_by = sources.get("staffing_plan_by") or {}
    staffing_plan_path = (sources.get("_paths") or {}).get("staffing_plan")
    staffing_mapping_by_cc = sources.get("staffing_mapping_by_cc") or {}
    staffing_source_validated = bool(sources.get("staffing_source_validation_passed"))
    sp_conflicts_by_key = {}
    for c in sources.get("staffing_plan_conflicts") or []:
        sp_conflicts_by_key.setdefault(c.get("budget_code_key"), []).append(c)

    for key in sorted(canonical_keys):
        cost_code = key.split(".")[1] if "." in key else None
        ctx = sources["context_by"].get(key, {})
        actuals = (ctx.get("actuals") or {})
        budg = (ctx.get("budget_amounts") or {})
        opa = (ctx.get("owner_pay_app") or {})
        spa = (ctx.get("procore_subcontractor_pay_apps") or {})
        rec = sources["rec_by"].get(key, {})
        trend = sources["trend_by"].get(key, {})
        sched = sources["sched_by"].get(key, {})
        conf = sources["conf_by"].get(key, {})
        mconf = sources["monthly_conf_by"].get(key, {})
        mdist = sources["monthly_dist_by"].get(key, {})
        pfin = sources["prob_final_by"].get(key, {})
        psim = sources["prob_sim_by"].get(key, {})
        hadj = sources["hist_adj_by"].get(key, {})
        hrel = sources["hist_rel_by"].get(key, {})
        hval = sources["hist_val_by"].get(key, {})
        hmon = sources["hist_mon_by"].get(key, {})
        hprob = sources["hist_prob_by"].get(key, {})
        freq = sources["freq_by"].get(key, {})
        fphase = sources["freq_phasing_by"].get(key, {})

        def add(family, ptype, src_file, signal, value, _key=key, **kw):
            items.append(es.evidence_item(project_key, _key, ptype,
                                          str(paths.get(ptype)) if paths.get(ptype) else None,
                                          src_file, _key, family, signal, value, **kw))

        # ---- actuals truth + budget references (CostEntries is accounting truth; refs are NOT caps) ----
        if actuals:
            add(es.F_ACTUAL, "context", "summaries/budget_code_forecast_context.jsonl",
                "actual_cost_all_source_to_date", actuals.get("actual_cost_all_source_to_date"),
                confidence="high", recency=actuals.get("latest_actual_accounting_date"),
                supports_final_cost=True, reason_codes=["accounting_truth", "hard_floor"])
        if budg:
            add(es.F_BUDGET, "context", "summaries/budget_code_forecast_context.jsonl",
                "revised_budget", budg.get("revised_budget"), reason_codes=["reference_only_never_cap"])
            add(es.F_PROJECTED, "context", "summaries/budget_code_forecast_context.jsonl",
                "projected_costs", budg.get("projected_costs"), reason_codes=["reference_only_never_cap"])
        if rec.get("owner_scope_value") is not None:
            add(es.F_OWNER_SCOPE, "intelligence", "forecast_recommendations_by_budget_code.jsonl",
                "owner_scope_value", rec.get("owner_scope_value"), reason_codes=["reference_only_never_cap"])
        if opa.get("latest_current_value") is not None:
            add(es.F_OWNER_PAYAPP, "context", "summaries/budget_code_forecast_context.jsonl",
                "owner_pay_app_current_value", opa.get("latest_current_value"),
                reason_codes=["progress_evidence_not_actual_cost"])
        if spa.get("latest_total_completed_and_stored_to_date_sum") is not None:
            add(es.F_SUB_PAYAPP, "context", "summaries/budget_code_forecast_context.jsonl",
                "subcontractor_completed_to_date", spa.get("latest_total_completed_and_stored_to_date_sum"),
                reason_codes=["progress_evidence_not_actual_cost"])

        # ---- cost-entry trend + schedule + accuracy/confidence ----
        if trend:
            add(es.F_COST_TREND, "intelligence", "trend_evidence_by_budget_code.jsonl",
                "trend_signal", trend.get("trend_signal"), direction=trend.get("burn_acceleration_class"),
                confidence=conf.get("calibrated_confidence"), supports_final_cost=True,
                supports_monthly_phasing=True, supports_probability=True)
        if sched:
            add(es.F_SCHED_REMAIN, "intelligence", "schedule_forecast_evidence_by_budget_code.jsonl",
                "schedule_remaining_work_status", sched.get("schedule_remaining_work_status"),
                confidence=sched.get("schedule_confidence"),
                supports_monthly_phasing=bool(sched.get("influences_code_estimate")),
                reason_codes=([] if sched.get("influences_code_estimate") else ["schedule_context_only"]))
        if mconf:
            add(es.F_SCHED_MONTHLY, "monthly", "monthly_forecast_confidence_by_budget_code.jsonl",
                "monthly_forecast_basis", mconf.get("monthly_forecast_basis"), supports_monthly_phasing=True)
        if conf:
            add(es.F_ACCURACY, "intelligence", "forecast_confidence_by_budget_code.jsonl",
                "calibrated_confidence", conf.get("calibrated_confidence"),
                confidence=conf.get("calibrated_confidence"))

        # ---- base accepted models ----
        if rec:
            add(es.F_INTELLIGENCE, "intelligence", "forecast_recommendations_by_budget_code.jsonl",
                "recommended_final_cost", rec.get("recommended_final_cost"),
                direction=rec.get("forecast_direction"), confidence=rec.get("confidence_score"),
                supports_final_cost=True, reason_codes=["accepted_base_final_cost"])
        if mconf:
            add(es.F_MONTHLY, "monthly", "monthly_forecast_confidence_by_budget_code.jsonl",
                "source_shares", mconf.get("source_shares"), supports_monthly_phasing=True,
                reason_codes=["accepted_base_monthly"])
        if pfin:
            add(es.F_PROBABILITY, "probability", "probabilistic_final_cost_by_budget_code.jsonl",
                "simulated_p50", pfin.get("simulated_p50"), supports_probability=True,
                reason_codes=["accepted_base_probability"])

        # ---- advisory: history-informed (3 families) ----
        rel_score = hrel.get("overall_history_reliability_score")
        vclass = hval.get("validation_class")
        if hadj:
            add(es.F_HIST_FINAL, "history_informed",
                "history_informed_forecast_adjustment_by_budget_code.jsonl",
                "history_informed_adjusted_final_cost", hadj.get("history_informed_adjusted_final_cost"),
                direction=hadj.get("history_informed_direction"), confidence=rel_score,
                contradiction_score=hval.get("actual_trend_override_score") or "0.0000",
                supports_final_cost=True, requires_human_acceptance=True, do_not_auto_apply=True,
                reason_codes=[f"reliability_band={hrel.get('reliability_band')}", f"validation={vclass}"])
        if hmon:
            add(es.F_HIST_MONTHLY, "history_informed",
                "history_informed_monthly_distribution_by_budget_code.jsonl",
                "history_curve_weight_suggestion", hmon.get("history_curve_weight_suggestion"),
                confidence=rel_score, supports_monthly_phasing=True, requires_human_acceptance=True,
                do_not_auto_apply=True)
        if hprob:
            add(es.F_HIST_PROB, "history_informed",
                "history_informed_probability_adjustments_by_budget_code.jsonl",
                "suggested_sigma_multiplier", hprob.get("suggested_sigma_multiplier"),
                direction=hprob.get("suggested_probability_direction"), confidence=rel_score,
                supports_probability=True, requires_human_acceptance=True, do_not_auto_apply=True)

        # ---- advisory: cost-frequency cadence + staffing rate ----
        if freq:
            add(es.F_FREQ_CADENCE, "cost_frequency", "cost_frequency_by_budget_code.jsonl",
                "effective_frequency_class", freq.get("effective_frequency_class"),
                confidence=freq.get("frequency_confidence"), supports_monthly_phasing=True,
                requires_human_acceptance=True,
                reason_codes=["timing_only_never_final_cost"])
            if freq.get("is_internal_staffing_code") and freq.get("daily_rate"):
                add(es.F_STAFFING_RATE, "cost_frequency", "internal_staffing_daily_rate_by_budget_code.jsonl",
                    "daily_rate", freq.get("daily_rate"), confidence=freq.get("daily_rate_confidence"),
                    supports_monthly_phasing=True, reason_codes=["timing_only_never_final_cost"])

        # ---- operator forecast control (explicit human decision; never model truth) ----
        ctrl_apps = ctrl_apps_by_key.get(key, [])
        decision = ctrl_by_key.get(key)
        if ctrl_apps:
            cid = (decision or {}).get("control_id") or ctrl_apps[0].get("control_id")
            items.append(es.evidence_item(
                project_key, key, "operator_control", ctrl_file, "code_forecast_controls.jsonl", cid,
                es.F_OPERATOR_CONTROL, "operator_control_type",
                (decision or {}).get("control_type") or ctrl_apps[0].get("control_type"),
                direction="stop_or_reduce", confidence="operator_decision",
                supports_final_cost=bool(decision and decision.get("dollar_applied")),
                supports_monthly_phasing=bool(decision and decision.get("timing_applied")),
                requires_human_acceptance=True, do_not_auto_apply=(decision is None),
                reason_codes=[a.get("disposition") for a in ctrl_apps],
                notes="operator decision; pending controls queued only; applied only when accepted"))

        # ---- operator staffing plan (operator-supplied planned staffing; advisory final-cost evidence) ----
        sp_row = staffing_plan_by.get(key)
        sp_conflicts = sp_conflicts_by_key.get(key, [])
        if sp_row:
            add(es.F_OPERATOR_STAFFING_PLAN, "staffing_plan",
                "staffing_plan_summary_by_budget_code.jsonl",
                "staffing_plan_implied_final_cost", sp_row.get("staffing_plan_implied_final_cost"),
                direction="operator_planned_staffing", confidence="operator_supplied",
                supports_final_cost=True, supports_monthly_phasing=True,
                requires_human_acceptance=True, do_not_auto_apply=True,
                reason_codes=["operator_planned_staffing_lab_only", sp_row.get("recommendation_status"),
                              ("requires_operator_acceptance" if sp_row.get("requires_operator_acceptance")
                               else "within_materiality")],
                notes="operator-supplied planned staffing; LAB-only numeric; plan-implied final cost is "
                      "advisory until explicit operator acceptance")

        per_code[key] = {
            "actual_cost_to_date": actuals.get("actual_cost_all_source_to_date"),
            "revised_budget": budg.get("revised_budget"), "projected_costs": budg.get("projected_costs"),
            "rec": rec, "trend": trend, "sched": sched, "conf": conf,
            "monthly_conf": mconf, "monthly_dist": mdist,
            "prob_final": pfin, "prob_sim": psim,
            "hist_adj": hadj, "hist_rel": hrel, "hist_val": hval, "hist_mon": hmon, "hist_prob": hprob,
            "freq": freq, "freq_phasing": fphase,
            "owner_pay_app": opa, "sub_pay_app": spa,
            "operator_control": decision, "operator_control_apps": ctrl_apps,
            "staffing_plan": sp_row, "staffing_plan_conflicts": sp_conflicts,
            "dormant": (sources.get("dormant_by") or {}).get(key),
            # staffing-basis gating: mapping acceptance (by source cost_code) + validated source
            "staffing_mapping_status": (staffing_mapping_by_cc.get(cost_code) or {}).get("mapping_status"),
            "staffing_applied_numeric": bool((staffing_mapping_by_cc.get(cost_code) or {}).get("applied_numeric")),
            "staffing_source_validation_passed": staffing_source_validated,
        }
    return items, per_code
