"""forecast_staffing_plan apply: dual monthly forecast, bridge deltas, floor, reconciliation, conflicts."""
from decimal import Decimal

from construction_financial_review.common.money import D
from construction_financial_review.forecast_staffing_plan import apply as sapply
from construction_financial_review.forecast_staffing_plan import mapping as smap

CC = "10-01-314"
KEY = "1000.10-01-314.LAB"
CANON = [{"budget_code_key": f"1000.{CC}.{c}", "cost_code": CC, "category": c,
          "budget_code_description": f"X.SUPERINTENDENT 2.{c}"} for c in ("LAB", "LBN", "MAT")]
CFG_SP = {"materiality_threshold": "25000.00", "zero_after_staffing_plan_end": True}


def _mapping(require_acceptance=True):
    fam = smap.build_canonical_family_index(CANON)
    keys = {r["budget_code_key"] for r in CANON}
    overrides = {CC: [{"target_budget_code_key": KEY, "acceptance_status": "accepted",
                       "allocation_share": "1.0000"}]}
    return [smap.resolve_cost_code(CC, fam, keys, overrides, require_acceptance)]


def _discovery(monthly):
    return {"parsed": {"monthly_by_cost_code": [{"cost_code": CC, "monthly_forecast": monthly}],
                       "normalized": [], "project_forecast": [], "summary_by_person": []}}


def _resolve(monthly, actual, accepted_ctc, accepted_final):
    disc = _discovery(monthly)
    rec = {KEY: {"recommended_cost_to_complete": accepted_ctc, "recommended_final_cost": accepted_final}}
    return sapply.resolve(disc, _mapping(), {KEY: D(actual)}, rec, CFG_SP, "tropical")


def test_dual_vectors_reconcile_and_floor_preserved():
    monthly = {"2026-06": "40000.00", "2026-07": "41000.00"}
    res = _resolve(monthly, "469248.48", "250931.13", "720179.61")
    d = res["by_key"][KEY]
    # plan-implied monthly sums to the plan total; ctc-reconciled monthly sums to the accepted CTC
    assert sum(d["implied_monthly"].values(), Decimal("0")) == Decimal("81000.00")
    assert sum(d["ctc_reconciled_monthly"].values(), Decimal("0")) == Decimal("250931.13")
    # implied final = actual + plan remaining; floor preserved
    assert d["plan_implied_final_cost"] == Decimal("469248.48") + Decimal("81000.00")
    assert d["plan_implied_final_cost"] >= d["actual_cost_to_date"]
    assert not res["reconciliation_failures"]
    assert not res["any_floor_violation"]


def test_material_delta_flags_acceptance_and_stale_ctc_conflict():
    # plan remaining (81k) is materially BELOW accepted CTC (250.9k) -> stale/excessive accepted CTC
    res = _resolve({"2026-06": "40000.00", "2026-07": "41000.00"}, "469248.48", "250931.13", "720179.61")
    d = res["by_key"][KEY]
    assert d["requires_operator_acceptance"] is True
    classes = {c["conflict_class"] for c in res["conflicts"]}
    assert "staffing_plan_conflicts_with_current_accepted_ctc" in classes
    assert "staffing_plan_changes_final_cost_materially" in classes


def test_plan_above_accepted_ctc_also_flagged():
    # plan remaining (109k) materially ABOVE accepted CTC (23k) -> accepted CTC understates
    res = _resolve({"2026-06": "54000.00", "2026-07": "55045.44"}, "299380.32", "23145.65", "322525.97")
    d = res["by_key"][KEY]
    assert d["plan_implied_remaining_cost"] == Decimal("109045.44")
    assert d["requires_operator_acceptance"] is True
    classes = {c["conflict_class"] for c in res["conflicts"]}
    assert "staffing_plan_conflicts_with_current_accepted_ctc" in classes


def test_immaterial_delta_does_not_require_acceptance():
    # plan remaining within $25k of accepted CTC -> no acceptance required, no stale-ctc conflict
    res = _resolve({"2026-06": "50000.00", "2026-07": "50000.00"}, "100000.00", "100000.00", "200000.00")
    d = res["by_key"][KEY]
    assert d["requires_operator_acceptance"] is False
    classes = {c["conflict_class"] for c in res["conflicts"]}
    assert "staffing_plan_conflicts_with_current_accepted_ctc" not in classes
    assert "staffing_plan_changes_final_cost_materially" not in classes


def test_no_accepted_rec_marks_recommendation_only():
    # a mapped code with no accepted recommendation -> acceptance required (recommendation-only)
    disc = _discovery({"2026-06": "40000.00"})
    res = sapply.resolve(disc, _mapping(), {KEY: D("0")}, {}, CFG_SP, "tropical")
    d = res["by_key"][KEY]
    assert d["accepted_cost_to_complete"] is None
    assert d["requires_operator_acceptance"] is True
    assert d["ctc_reconciled_monthly"] is None  # nothing to reconcile to
    assert d["plan_implied_final_cost"] == Decimal("40000.00")
