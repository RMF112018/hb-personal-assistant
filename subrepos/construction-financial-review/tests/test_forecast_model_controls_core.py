"""forecast_model_controls: synthetic unit tests for window, value constraints, shapes, manual, floor.

These run without the live data root — they exercise the pure resolver + shape vocabulary directly.
"""
from __future__ import annotations

from decimal import Decimal

from construction_financial_review.forecast_model_controls import apply
from construction_financial_review.forecast_model_controls import control_schema as cs
from construction_financial_review.forecast_model_controls import integration
from construction_financial_review.forecast_model_controls import mapping as cmap
from construction_financial_review.forecast_model_controls import model_shapes

KEY = "1000.10-01-800.SUB"
OTHER = "1000.15-07-590.SUB"
CANON = {KEY, OTHER}
AMOUNTS = {KEY: {"projected_costs": "500000.00", "revised_budget": "480000.00",
                 "original_budget_amount": "450000.00", "committed_costs": "460000.00"}}
REC = {KEY: {"recommended_final_cost": "512345.67", "recommended_cost_to_complete": "137345.67"}}
ACTUALS = {KEY: Decimal("375000.00"), OTHER: Decimal("100.00")}
SCHEDULE = {KEY: {"latest_remaining_finish": "2026-09-15", "earliest_remaining_start": "2026-06-10"}}
PROJECT_SCHEDULE = {"schedule_present": True, "latest_project_schedule_date": "2026-10-31"}
CAL = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
MODEL_FINAL = {KEY: Decimal("512345.67")}
MODEL_CTC = {KEY: Decimal("137345.67")}
REF_CTX = integration.build_ref_ctx(CANON, AMOUNTS, REC)


def _ctrl(**kw):
    base = {"project_key": "tropical", "control_id": "c1", "budget_code_key": KEY, "cost_code": None,
            "control_type": "forecast_model_control", "effective_month": "2026-06",
            "acceptance_status": "accepted", "requires_human_acceptance": True,
            "accepted_by": "Bobby Fetting", "accepted_at": "2026-06-16", "reason": "test"}
    base.update(kw)
    return base


def _run(controls, cfg=None):
    norm = [cs.normalize_control(c) for c in controls]
    lr = {"controls": norm}
    cc = cmap.cost_code_to_keys(CANON)
    mr = [cmap.map_control(c, CANON, cc) for c in norm]
    return apply.resolve(lr, mr, cfg or {}, ACTUALS, REF_CTX, SCHEDULE, PROJECT_SCHEDULE, CAL,
                         MODEL_FINAL, MODEL_CTC, "tropical")


# ---- value constraints ----

def test_equal_to_reference_projected_cost():
    d = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="projected_cost")])["by_key"][KEY]
    assert d["controlled_final_cost"] == Decimal("500000.00")
    assert d["controlled_remaining"] == Decimal("125000.00")
    assert d["changes_deterministic_final"] is True
    assert sum(d["monthly_allocation"].values()) == Decimal("125000.00")


def test_equal_to_original_and_revised_budget():
    for src, val in (("original_budget", "450000.00"), ("revised_budget", "480000.00")):
        d = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source=src)])["by_key"][KEY]
        assert d["controlled_final_cost"] == Decimal(val)


def test_equal_to_committed_and_intelligence_final():
    d = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="committed_cost")])["by_key"][KEY]
    assert d["controlled_final_cost"] == Decimal("460000.00")
    d = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="accepted_intelligence_final")])["by_key"][KEY]
    assert d["controlled_final_cost"] == Decimal("512345.67")


def test_not_to_exceed_binds_and_noop():
    # ref 480k < model 512k -> binds (lowers), disclosed
    d = _run([_ctrl(value_constraint_policy="not_to_exceed_reference", reference_source="revised_budget")])["by_key"][KEY]
    assert d["controlled_final_cost"] == Decimal("480000.00") and d["constraint_applied"] and d["changes_deterministic_final"]
    # ref 600k > model -> no-op (still applies, no value change)
    d = _run([_ctrl(value_constraint_policy="not_to_exceed_reference", reference_source="explicit_user_amount",
                    explicit_value_amount="600000.00")])["by_key"][KEY]
    assert d["controlled_final_cost"] == Decimal("512345.67") and not d["changes_deterministic_final"]


def test_not_less_than_binds():
    d = _run([_ctrl(value_constraint_policy="not_less_than_reference", reference_source="explicit_user_amount",
                    explicit_value_amount="600000.00")])["by_key"][KEY]
    assert d["controlled_final_cost"] == Decimal("600000.00") and d["constraint_applied"]


def test_explicit_final_and_remaining():
    d = _run([_ctrl(value_constraint_policy="explicit_final_value", explicit_value_amount="505000.00")])["by_key"][KEY]
    assert d["controlled_final_cost"] == Decimal("505000.00")
    d = _run([_ctrl(value_constraint_policy="explicit_remaining_value", explicit_value_amount="100000.00")])["by_key"][KEY]
    assert d["controlled_final_cost"] == Decimal("475000.00") and d["controlled_remaining"] == Decimal("100000.00")


# ---- floor / acceptance / duplicates ----

def test_target_below_actuals_fails_closed():
    r = _run([_ctrl(value_constraint_policy="explicit_final_value", explicit_value_amount="100000.00")])
    assert KEY not in r["by_key"] and r["any_floor_conflict"]


def test_pending_and_rejected_do_not_apply_or_gate():
    r = _run([_ctrl(acceptance_status="pending", value_constraint_policy="explicit_final_value",
                    explicit_value_amount="100000.00")])
    assert not r["by_key"] and not r["any_floor_conflict"]
    r = _run([_ctrl(acceptance_status="rejected", value_constraint_policy="equal_to_reference",
                    reference_source="projected_cost")])
    assert not r["by_key"]


def test_duplicate_conflicting_fails_closed():
    r = _run([_ctrl(control_id="a", value_constraint_policy="equal_to_reference", reference_source="projected_cost"),
              _ctrl(control_id="b", value_constraint_policy="equal_to_reference", reference_source="revised_budget")])
    assert r["any_duplicate_conflict"] and KEY not in r["by_key"]


def test_unknown_reference_and_missing_reference_fail_closed():
    r = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="revised_budget",
                    budget_code_key=OTHER)])  # OTHER has no amounts
    assert r["any_missing_reference"] and OTHER not in r["by_key"]


# ---- window ----

def test_window_explicit_end_shrinks_active_months():
    d = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="projected_cost",
                    forecast_end_policy="explicit_date", forecast_end_date="2026-07-31")])["by_key"][KEY]
    assert d["active_months"] == ["2026-06", "2026-07"]
    assert sum(d["monthly_allocation"].values()) == Decimal("125000.00")


def test_window_default_uses_project_schedule_final():
    d = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="projected_cost")])["by_key"][KEY]
    assert d["schedule_end_basis"] == "project_schedule_final_date"
    assert d["active_months"] == CAL


def test_impossible_window_fails_closed():
    r = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="projected_cost",
                    forecast_start_policy="explicit_date", forecast_start_date="2030-01-01")])
    assert r["any_impossible_window"] and KEY not in r["by_key"]


# ---- model shapes ----

def test_shape_only_timing_no_value_change():
    d = _run([_ctrl(model_type="linear_ascending")])["by_key"][KEY]
    assert not d["changes_deterministic_final"]
    assert d["controlled_remaining"] == Decimal("137345.67")
    vals = list(d["monthly_allocation"].values())
    assert vals[-1] > vals[0]


def test_each_shape_reconciles_to_ctc():
    for mt in ("linear", "linear_ascending", "linear_descending", "front_loaded_s_curve",
               "back_loaded_s_curve", "bell_curve"):
        d = _run([_ctrl(model_type=mt, value_constraint_policy="equal_to_reference",
                        reference_source="projected_cost")])["by_key"][KEY]
        assert sum(d["monthly_allocation"].values()) == Decimal("125000.00"), mt


def test_bell_alias_belle():
    assert cs.normalize_model_type("belle") == "bell_curve"


def test_shape_vector_shapes():
    w = model_shapes.shape_weights("linear_descending", ["a", "b", "c"])
    vals = list(w.values())
    assert vals[0] > vals[-1]
    assert model_shapes.shape_weights("existing_model", ["a"]) is None


# ---- manual ----

def test_manual_monthly_applies_and_reconciles():
    d = _run([_ctrl(model_type="manual_monthly",
                    manual_monthly_values={"2026-06": "20000.00", "2026-07": "30000.00", "2026-08": "50000.00"})])["by_key"][KEY]
    assert d["controlled_remaining"] == Decimal("100000.00")
    assert d["controlled_final_cost"] == Decimal("475000.00")
    assert d["monthly_allocation"]["2026-06"] == Decimal("20000.00")


def test_manual_monthly_out_of_window_fails():
    r = _run([_ctrl(model_type="manual_monthly", manual_monthly_values={"2027-01": "5000.00"})])
    assert r["any_manual_invalid"] and KEY not in r["by_key"]


def test_manual_total_distributes():
    d = _run([_ctrl(model_type="manual_total", manual_remaining_cost="60000.00",
                    manual_total_distribution_policy="linear")])["by_key"][KEY]
    assert d["controlled_remaining"] == Decimal("60000.00")
    assert sum(d["monthly_allocation"].values()) == Decimal("60000.00")


def test_manual_monthly_conflicts_with_equality_fails():
    r = _run([_ctrl(model_type="manual_monthly", value_constraint_policy="equal_to_reference",
                    reference_source="projected_cost",
                    manual_monthly_values={"2026-06": "10000.00"})])  # implies final 385k != 500k
    assert r["any_manual_invalid"] and KEY not in r["by_key"]


# ---- probability assessment (degraded-not-fatal) ----

def test_probability_anchor_when_prior_row_present():
    from construction_financial_review.forecast_model_controls import probability_assessment as pa
    d = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="projected_cost")])["by_key"][KEY]
    row = pa.assess("tropical", d, AMOUNTS[KEY], prior_prob_present=True, historical_burn=None,
                    within_pct=Decimal("0.10"))
    assert row["probability_status"] == "accepted_probability_anchor"


def test_probability_provisional_when_no_prior_row():
    from construction_financial_review.forecast_model_controls import probability_assessment as pa
    d = _run([_ctrl(value_constraint_policy="equal_to_reference", reference_source="projected_cost")])["by_key"][KEY]
    row = pa.assess("tropical", d, AMOUNTS[KEY], prior_prob_present=False, historical_burn=None,
                    within_pct=Decimal("0.10"))
    assert row["probability_status"] == "provisional_manual_value_assessment"
    # numeric probabilities are null for provisional; classification + score + confidence required
    assert row["probability_final_cost_at_or_below_controlled_value"] is None
    assert row["probability_final_cost_exceeds_controlled_value"] is None
    assert row["manual_value_assessment"] in (
        "supported", "plausible", "aggressive", "conservative", "weakly_supported", "unsupported")
    assert row["evidence_support_score"] is not None and row["confidence"] is not None
    assert row["data_gaps"] is not None


def test_probability_insufficient_evidence():
    from construction_financial_review.forecast_model_controls import probability_assessment as pa
    # only the model_final reference present (<2 references) -> insufficient
    d = _run([_ctrl(value_constraint_policy="explicit_final_value", explicit_value_amount="500000.00")])["by_key"][KEY]
    row = pa.assess("tropical", d, {}, prior_prob_present=False, historical_burn=None,
                    within_pct=Decimal("0.10"))
    assert row["probability_status"] == "probability_unavailable_insufficient_evidence"
    assert row["manual_value_assessment"] == "insufficient_evidence"
