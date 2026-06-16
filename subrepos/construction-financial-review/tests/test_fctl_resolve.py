"""forecast_controls: precedence resolution, acceptance gating, floor preservation, supersession."""
from __future__ import annotations

from decimal import Decimal

from construction_financial_review.forecast_controls import apply
from construction_financial_review.forecast_controls import control_schema as cs
from construction_financial_review.forecast_controls import mapping as cmap

KEY = "1000.15-07-590.SUB"
CANON = {KEY, "1000.10-01-100.LAB"}
ACTUALS = {KEY: Decimal("1385588.66")}
CFG = {
    "require_accepted_status_for_final_cost_change": True,
    "require_accepted_status_for_post_stop_zero": True,
    "allow_pending_timing_controls": False,
    "preserve_actuals_floor": True,
    "allow_pending_controls_in_review_queue": True,
}


def _ctrl(**kw):
    base = {
        "project_key": "tropical", "budget_code_key": KEY, "cost_code": "15-07-590",
        "control_type": "closeout_stop_date", "forecast_stop_date": "2026-07-31",
        "acceptance_status": "pending", "requires_human_acceptance": True, "accepted_by": None,
        "accepted_at": None, "acceptance_notes": None, "source": "operator_decision", "reason": "r",
        "accepted_remaining_cost": None, "accepted_final_cost": None,
    }
    base.update(kw)
    return cs.normalize_control(base, "20260101_000000")


def _resolve(controls):
    idx = cmap.cost_code_to_keys(CANON)
    mres = [cmap.map_control(c, CANON, idx) for c in controls]
    load_result = {"controls": controls}
    return apply.resolve(load_result, mres, CFG, ACTUALS, "tropical")


def test_pending_control_queued_not_applied():
    r = _resolve([_ctrl(control_id="p1")])
    assert KEY not in r["by_key"]
    assert any(q["control_id"] == "p1" for q in r["review_queue"])
    assert r["applications"][0]["disposition"] == "pending_not_applied"


def test_accepted_stop_date_applied_timing_only():
    r = _resolve([_ctrl(control_id="a1", acceptance_status="accepted", accepted_by="Bobby")])
    d = r["by_key"][KEY]
    assert d["timing_applied"] is True and d["dollar_applied"] is False
    assert d["dollars_model_derived"] is True and d["stop_month"] == "2026-07"


def test_accepted_final_below_actuals_fails():
    r = _resolve([_ctrl(control_id="a2", control_type="accepted_final_cost_override",
                        acceptance_status="accepted", accepted_by="Bobby",
                        accepted_final_cost="1000000.00")])
    assert r["any_floor_violation"] is True
    assert KEY not in r["by_key"]
    assert any("below" in q["review_reason"] for q in r["review_queue"])


def test_accepted_remaining_allowance_preserves_floor():
    r = _resolve([_ctrl(control_id="a3", control_type="remaining_cost_allowance",
                        acceptance_status="accepted", accepted_by="Bobby",
                        accepted_remaining_cost="15000.00")])
    d = r["by_key"][KEY]
    assert d["dollar_applied"] is True
    assert d["accepted_remaining_cost"] == Decimal("15000.00")
    assert r["any_floor_violation"] is False


def test_pending_superseded_by_accepted():
    controls = [
        _ctrl(control_id="pend"),
        _ctrl(control_id="zacc", acceptance_status="accepted", accepted_by="Bobby"),
    ]
    r = _resolve(controls)
    assert r["by_key"][KEY]["control_id"] == "zacc"
    apps = {a["control_id"]: a for a in r["applications"]}
    assert apps["pend"]["disposition"] == "superseded_by_accepted_control"
    assert apps["pend"]["superseded_by"] == "zacc"


def test_watch_only_changes_nothing():
    r = _resolve([_ctrl(control_id="w1", control_type="watch_only", acceptance_status="accepted",
                        accepted_by="Bobby")])
    assert KEY not in r["by_key"]
    assert r["applications"][0]["disposition"] == "watch_only_no_change"
