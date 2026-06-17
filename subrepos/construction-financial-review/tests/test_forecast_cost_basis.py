"""Unit tests for the deterministic BudgetDetails cost-basis module (forecast_cost_basis)."""
from decimal import Decimal as D

from construction_financial_review.forecast_cost_basis import (
    classify_budgetdetails_cost_basis,
    validate_cost_basis_decisions,
)
from construction_financial_review.forecast_cost_basis.apply import (
    apply_cost_basis_decision,
    build_cost_basis_audit_row,
)


def _apply(inp):
    final = D(inp.get("inbound_recommended_final", inp.get("pre_cost_basis_model_final", "0")))
    ctc = D(inp.get("inbound_recommended_ctc", inp.get("pre_cost_basis_model_ctc", "0")))
    actual = D(inp.get("actual_cost_to_date", "0"))
    return apply_cost_basis_decision(final, ctc, actual, inp)


# 1 — committed projected-cost basis (the canonical defect)
def test_committed_projected_cost_basis():
    inp = dict(budget_code_key="1000.15-01-426.MAT", cost_code="15-01-426", category="MAT",
               actual_cost_to_date="27778.50", committed_costs="25000.00", commitment_invoiced="0.00",
               erp_direct_costs="27778.50", pending_cost_changes="0.00", projected_costs="52778.50",
               pre_cost_basis_model_final="29615.78", pre_cost_basis_model_ctc="1837.28")
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "budgetdetails_projected_cost_basis"
    assert nf == D("52778.50") and nc == D("25000.00")
    assert d["projected_cost_formula_reconciles"] is True


# 2 — zero committed cost, no remaining evidence -> suppress to actuals
def test_zero_committed_no_evidence_suppressed():
    inp = dict(budget_code_key="x", actual_cost_to_date="100.00", committed_costs="0.00",
               erp_direct_costs="100.00", pending_cost_changes="0.00", projected_costs="100.00",
               pre_cost_basis_model_final="100.00", pre_cost_basis_model_ctc="0.00")
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "suppressed_no_remaining_commitment"
    assert nc == D("0.00") and nf == D("100.00")


# 3 — projected cost below actuals -> actuals floor preserved (defensive)
def test_projected_below_actuals_floor():
    inp = dict(budget_code_key="x", actual_cost_to_date="100.00", committed_costs="10.00",
               erp_direct_costs="50.00", pending_cost_changes="0.00", projected_costs="60.00",
               pre_cost_basis_model_final="100.00", pre_cost_basis_model_ctc="0.00")
    nf, nc, d = _apply(inp)
    assert d["floor_applied"] is True
    assert "projected_cost_below_actuals" in d["reason"]
    assert nf == D("100.00") and nc == D("0.00")
    assert d["cost_basis_status"] != "budgetdetails_projected_cost_basis"


# 4 — accepted manual_monthly operator control wins; basis does not override
def test_manual_monthly_operator_control_wins():
    inp = dict(budget_code_key="1000.15-16-110.SUB", actual_cost_to_date="100.00",
               committed_costs="5000.00", erp_direct_costs="100.00", pending_cost_changes="0.00",
               projected_costs="5100.00", pre_cost_basis_model_final="200.00",
               pre_cost_basis_model_ctc="100.00", inbound_recommended_final="300.00",
               inbound_recommended_ctc="200.00", operator_controlled=True)
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "operator_controlled"
    assert nf == D("300.00") and nc == D("200.00")   # operator value untouched by projected basis


# 5 — accepted explicit final / remaining control -> operator_controlled basis
def test_explicit_operator_value_control():
    inp = dict(budget_code_key="x", actual_cost_to_date="100.00", committed_costs="0.00",
               projected_costs="100.00", erp_direct_costs="100.00", pending_cost_changes="0.00",
               pre_cost_basis_model_final="180.00", pre_cost_basis_model_ctc="80.00",
               inbound_recommended_final="250.00", inbound_recommended_ctc="150.00",
               operator_controlled=True)
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "operator_controlled"
    assert nf == D("250.00")


# 6 — accepted not-to-exceed / not-less-than control is authoritative, disclosed as operator (not a cap)
def test_not_to_exceed_operator_control_authoritative():
    inp = dict(budget_code_key="x", actual_cost_to_date="100.00", committed_costs="900.00",
               erp_direct_costs="100.00", pending_cost_changes="0.00", projected_costs="1000.00",
               pre_cost_basis_model_final="500.00", pre_cost_basis_model_ctc="400.00",
               inbound_recommended_final="450.00", inbound_recommended_ctc="350.00",
               operator_controlled=True)
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "operator_controlled"
    assert nf == D("450.00")   # operator constraint result preserved, NOT replaced by projected 1000


# 7 — dormant / closed / recent-zero suppression remains authoritative
def test_dormant_suppression_authoritative():
    for status, expected in (("dormant_no_recent_cost", "dormant_suppressed"),
                             ("closed_do_not_use", "closed_suppressed"),
                             ("recent_zero_run_after_prior_activity", "recent_zero_run_suppressed")):
        inp = dict(budget_code_key="x", actual_cost_to_date="100.00", committed_costs="5000.00",
                   erp_direct_costs="100.00", pending_cost_changes="0.00", projected_costs="5100.00",
                   pre_cost_basis_model_final="100.00", pre_cost_basis_model_ctc="0.00",
                   dormant_suppressed=True, dormant_status=status)
        nf, nc, d = _apply(inp)
        assert d["cost_basis_status"] == expected
        assert nf == D("100.00") and nc == D("0.00")   # not revived by projected-cost basis


# 8 — formula mismatch -> manual_review_required, never silently projected basis
def test_formula_mismatch_manual_review():
    inp = dict(budget_code_key="x", actual_cost_to_date="100.00", committed_costs="50.00",
               erp_direct_costs="100.00", pending_cost_changes="0.00", projected_costs="999.00",
               pre_cost_basis_model_final="120.00", pre_cost_basis_model_ctc="20.00")
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "manual_review_required"
    assert d["validation_status"] == "manual_review"
    assert nf == D("120.00")   # model values kept; projected basis NOT used


# asymmetric guard — model overrun above projected is preserved (never capped to ERP)
def test_model_overrun_above_projected_preserved():
    inp = dict(budget_code_key="1000.15-03-010.SUB", actual_cost_to_date="9000.00",
               committed_costs="50000.00", erp_direct_costs="10141304.50", pending_cost_changes="0.00",
               projected_costs="10191304.50", pre_cost_basis_model_final="10253985.31",
               pre_cost_basis_model_ctc="10244985.31")
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "existing_model_basis"
    assert "model_final_above_projected_costs_preserved_no_erp_cap" in d["reason"]
    assert nf == D("10253985.31")   # overrun not lowered to ERP projected


# committed==0 with model-derived remaining -> existing model basis (not zeroed)
def test_zero_committed_with_model_remaining_preserved():
    inp = dict(budget_code_key="x", actual_cost_to_date="100.00", committed_costs="0.00",
               erp_direct_costs="100.00", pending_cost_changes="0.00", projected_costs="100.00",
               pre_cost_basis_model_final="160.00", pre_cost_basis_model_ctc="60.00")
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "existing_model_basis"
    assert d["affirmative_remaining_evidence"] is True
    assert nf == D("160.00") and nc == D("60.00")


# idempotency — an upstream-applied budgetdetails basis is preserved, not reclassified
def test_idempotent_upstream_basis_preserved():
    inp = dict(budget_code_key="1000.15-01-426.MAT", actual_cost_to_date="27778.50",
               committed_costs="25000.00", erp_direct_costs="27778.50", pending_cost_changes="0.00",
               projected_costs="52778.50", pre_cost_basis_model_final="29615.78",
               pre_cost_basis_model_ctc="1837.28", inbound_recommended_final="52778.50",
               inbound_recommended_ctc="25000.00",
               upstream_cost_basis_status="budgetdetails_projected_cost_basis")
    nf, nc, d = _apply(inp)
    assert d["cost_basis_status"] == "budgetdetails_projected_cost_basis"
    assert nf == D("52778.50") and nc == D("25000.00")


# validation gates over a small decision set
def test_validation_gates_pass_on_consistent_rows():
    rows, totals = [], {}
    for inp in (
        dict(budget_code_key="1000.15-01-426.MAT", cost_code="15-01-426", category="MAT",
             actual_cost_to_date="27778.50", committed_costs="25000.00", commitment_invoiced="0.00",
             erp_direct_costs="27778.50", erp_job_to_date_costs="27778.50", pending_cost_changes="0.00",
             projected_costs="52778.50", pre_cost_basis_model_final="29615.78",
             pre_cost_basis_model_ctc="1837.28"),
        dict(budget_code_key="z", cost_code="z", category="SUB", actual_cost_to_date="100.00",
             committed_costs="0.00", erp_direct_costs="100.00", pending_cost_changes="0.00",
             projected_costs="100.00", pre_cost_basis_model_final="100.00",
             pre_cost_basis_model_ctc="0.00"),
    ):
        d = classify_budgetdetails_cost_basis(inp)
        mt = D(d["selected_cost_to_complete"])
        totals[inp["budget_code_key"]] = mt
        rows.append(build_cost_basis_audit_row(d, monthly_total_after_basis=mt))
    checks = validate_cost_basis_decisions(rows, monthly_total_by_key=totals)
    assert all(checks.values()), [k for k, v in checks.items() if not v]
    assert checks["survey_code_1000_15_01_426_mat_projected_cost_basis"] is True
