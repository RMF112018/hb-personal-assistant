"""forecast_comprehensive wiring: operator_staffing_plan evidence family + conflict surfacing."""
from decimal import Decimal

from construction_financial_review.forecast_comprehensive import conflicts
from construction_financial_review.forecast_comprehensive import evidence_registry as er
from construction_financial_review.forecast_comprehensive import evidence_schema as es

KEY = "1000.10-01-314.LAB"
_EMPTY = ("context_by", "rec_by", "trend_by", "sched_by", "conf_by", "monthly_conf_by", "monthly_dist_by",
          "prob_final_by", "prob_sim_by", "hist_adj_by", "hist_rel_by", "hist_val_by", "hist_mon_by",
          "hist_prob_by", "freq_by", "freq_phasing_by", "freq_rate_by", "staffing_plan_monthly_by")

BRIDGE = {"budget_code_key": KEY, "cost_code": "10-01-314",
          "staffing_plan_implied_final_cost": "675528.64", "recommendation_status": "advisory",
          "requires_operator_acceptance": True}
SP_CONFLICT = {"project_key": "tropical", "budget_code_key": KEY, "cost_code": "10-01-314",
               "conflict_class": "staffing_plan_conflicts_with_current_accepted_ctc", "severity": "high",
               "detail": "x", "families_involved": ["operator_staffing_plan", "forecast_intelligence"],
               "requires_human_acceptance": True}


def _sources():
    src = {k: {} for k in _EMPTY}
    src["staffing_plan_by"] = {KEY: BRIDGE}
    src["staffing_plan_conflicts"] = [SP_CONFLICT]
    src["_paths"] = {"context": None, "intelligence": None, "monthly": None, "probability": None,
                     "history_informed": None, "cost_frequency": None, "staffing_plan": "/x/plan"}
    return src


def test_family_registered():
    assert es.F_OPERATOR_STAFFING_PLAN == "operator_staffing_plan"
    assert es.F_OPERATOR_STAFFING_PLAN in es.FAMILIES
    assert es.INDEPENDENCE_GROUP[es.F_OPERATOR_STAFFING_PLAN] == "staffing_plan"


def test_registry_emits_staffing_evidence_and_attaches_per_code():
    items, per_code = er.build_registry({KEY}, _sources(), "tropical")
    sp_items = [i for i in items if i["evidence_family"] == es.F_OPERATOR_STAFFING_PLAN]
    assert len(sp_items) == 1
    it = sp_items[0]
    assert it["independence_group"] == "staffing_plan"
    assert it["requires_human_acceptance"] is True and it["do_not_auto_apply"] is True
    assert per_code[KEY]["staffing_plan"] == BRIDGE
    assert per_code[KEY]["staffing_plan_conflicts"] == [SP_CONFLICT]


def test_conflicts_build_surfaces_staffing_conflicts():
    _items, per_code = er.build_registry({KEY}, _sources(), "tropical")
    sc = {"contradicted": False, "validation_class": "validated_aligned"}
    rows = conflicts.build("tropical", KEY, per_code[KEY], sc, Decimal("675528.64"))
    classes = {c["conflict_class"] for c in rows}
    assert "staffing_plan_conflicts_with_current_accepted_ctc" in classes
