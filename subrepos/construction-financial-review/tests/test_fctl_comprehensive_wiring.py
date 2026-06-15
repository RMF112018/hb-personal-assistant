"""forecast_controls: comprehensive wiring — evidence family, conflict classes, CLI registration."""
from __future__ import annotations

from decimal import Decimal

from construction_financial_review.cli import build_parser
from construction_financial_review.forecast_comprehensive import conflicts
from construction_financial_review.forecast_comprehensive import evidence_registry as er

KEY = "1000.15-07-590.SUB"
CANON = {KEY}


def _sources():
    return {
        "context_by": {KEY: {"actuals": {"actual_cost_all_source_to_date": "1385588.66"},
                             "budget_amounts": {"revised_budget": "1500000.00",
                                                "projected_costs": "1513192.33"}}},
        "rec_by": {}, "trend_by": {},
        "sched_by": {KEY: {"schedule_remaining_work_status": "open", "influences_code_estimate": True,
                           "schedule_confidence": "high"}},
        "conf_by": {}, "monthly_conf_by": {}, "monthly_dist_by": {}, "prob_final_by": {},
        "prob_overrun_by": {}, "prob_sim_by": {}, "hist_adj_by": {}, "hist_rel_by": {}, "hist_val_by": {},
        "hist_mon_by": {}, "hist_prob_by": {}, "hist_unmapped": [], "freq_by": {}, "freq_phasing_by": {},
        "freq_rate_by": {},
        "_paths": {"context": None, "intelligence": None, "monthly": None, "probability": None,
                   "history_informed": None, "cost_frequency": None},
    }


def _controls_ctx():
    decision = {"control_id": "a", "control_type": "closeout_stop_date", "timing_applied": True,
                "dollar_applied": False, "stop_month": "2026-07",
                "disposition": "applied_stop_date_timing_only"}
    return {"by_key": {KEY: decision},
            "apps_by_key": {KEY: [{"control_id": "a", "disposition": "applied_stop_date_timing_only"}]},
            "control_file": "code_forecast_controls.jsonl", "active": True}


def test_evidence_registry_includes_operator_forecast_control():
    items, per_code = er.build_registry(CANON, _sources(), "tropical", _controls_ctx())
    op = [i for i in items if i["evidence_family"] == "operator_forecast_control"]
    assert len(op) == 1
    assert op[0]["source_row_id"] == "a"
    assert op[0]["requires_human_acceptance"] is True
    assert per_code[KEY]["operator_control"]["control_id"] == "a"


def test_conflict_register_includes_operator_conflicts():
    items, per_code = er.build_registry(CANON, _sources(), "tropical", _controls_ctx())
    sc = {"contradicted": False, "validation_class": "ok"}
    out = conflicts.build("tropical", KEY, per_code[KEY], sc, Decimal("1704858.03"))
    classes = {c["conflict_class"] for c in out}
    assert "operator_control_conflicts_with_model_forecast" in classes
    assert "operator_stop_date_conflicts_with_schedule_remaining_work" in classes


def test_cli_registers_forecast_controls():
    args = build_parser().parse_args(["forecast-controls", "--project", "tropical"])
    assert args.command == "forecast-controls"
    assert args.project == "tropical"
