"""Evidence registry normalization + conflict classification + human acceptance + discovery."""
from decimal import Decimal

from tests._fc_fixtures import KEY, entry

from construction_financial_review.forecast_comprehensive import conflicts
from construction_financial_review.forecast_comprehensive import evidence_registry as reg
from construction_financial_review.forecast_comprehensive import evidence_schema as es
from construction_financial_review.forecast_comprehensive import evidence_scoring as scoring
from construction_financial_review.forecast_comprehensive import human_acceptance as ha

CFG = {"max_history_final_cost_weight": "0.45", "max_history_monthly_shape_weight": "0.30",
       "max_history_probability_weight": "0.25", "max_frequency_monthly_shape_weight": "0.60"}


def _sources_for(e):
    """Wrap one entry as the loaded-source maps for build_registry."""
    ctx = {"actuals": {"actual_cost_all_source_to_date": e["actual_cost_to_date"],
                       "latest_actual_accounting_date": "2026-05-01"},
           "budget_amounts": {"revised_budget": e["revised_budget"], "projected_costs": e["projected_costs"]},
           "owner_pay_app": e["owner_pay_app"], "procore_subcontractor_pay_apps": e["sub_pay_app"]}
    return {
        "context_by": {KEY: ctx}, "rec_by": {KEY: e["rec"]}, "trend_by": {KEY: e["trend"]},
        "sched_by": {KEY: e["sched"]}, "conf_by": {KEY: e["conf"]},
        "monthly_conf_by": {KEY: e["monthly_conf"]}, "monthly_dist_by": {KEY: e["monthly_dist"]},
        "prob_final_by": {KEY: e["prob_final"]}, "prob_overrun_by": {}, "prob_sim_by": {KEY: e["prob_sim"]},
        "hist_adj_by": {KEY: e["hist_adj"]}, "hist_rel_by": {KEY: e["hist_rel"]},
        "hist_val_by": {KEY: e["hist_val"]}, "hist_mon_by": {KEY: e["hist_mon"]},
        "hist_prob_by": {KEY: e["hist_prob"]}, "hist_unmapped": [],
        "freq_by": {KEY: e["freq"]}, "freq_phasing_by": {KEY: e["freq_phasing"]}, "freq_rate_by": {},
        "_paths": {"context": None, "intelligence": None, "monthly": None, "probability": None,
                   "history_informed": None, "cost_frequency": None},
    }


def test_registry_normalizes_multiple_families_with_lineage():
    items, per_code = reg.build_registry({KEY}, _sources_for(entry()), "tropical")
    fams = {i["evidence_family"] for i in items}
    for f in (es.F_ACTUAL, es.F_INTELLIGENCE, es.F_MONTHLY, es.F_PROBABILITY, es.F_HIST_FINAL,
              es.F_FREQ_CADENCE, es.F_COST_TREND):
        assert f in fams, f
    assert all(i["source_row_id"] == KEY and i["evidence_family"] for i in items)
    # actuals truth supports final cost (floor); pay-app families never support final cost
    actual = next(i for i in items if i["evidence_family"] == es.F_ACTUAL)
    assert actual["supports_final_cost"] is True


def test_conflicts_classified_usefully():
    # high probability over recommended + high confidence band => conflict
    e = entry(conf={"calibrated_confidence": "0.90", "confidence_band": "high"},
              prob_final={**entry()["prob_final"], "prob_exceeds_recommended_final_cost": "0.7000"})
    sc = scoring.score_code(e, CFG)
    cs = conflicts.build("tropical", KEY, e, sc, Decimal("109000.00"))
    classes = {c["conflict_class"] for c in cs}
    assert "probability_risk_contradicts_confidence_band" in classes
    # integrated 109000 vs projected 95000 -> divergence (within materiality? 14000 < 25000 -> not flagged)
    # cadence change flips on a conflict
    e2 = entry(freq={**entry()["freq"], "cadence_change_detected": True, "cadence_change_basis": "x"})
    cs2 = conflicts.build("tropical", KEY, e2, scoring.score_code(e2, CFG), Decimal("109000.00"))
    assert "frequency_cadence_contradicts_recent_actuals" in {c["conflict_class"] for c in cs2}


def test_human_acceptance_defaults_pending():
    row = ha.stamp({})
    assert row["acceptance_status"] == "pending"
    assert row["accepted_by"] is None and row["accepted_at"] is None
    assert row["requires_human_acceptance"] is True and row["do_not_auto_apply"] is True
