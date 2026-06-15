"""GC-fee proportionality: confirmed only when fee decline tracks 15-* progress with a stable total."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import gcgr_proportionality as gp


def _fee_rows(pairs):
    return [{"history_source_package": "cash_flow", "snapshot_month": snap, "cost_code": "20-18-110",
             "description": "CONTRACTORS FEE", "period_month": "2099-01", "classification": "forecast",
             "amount": Decimal(str(amt)), "source_row": 1} for snap, amt in pairs]


def _cow_context(increments):
    """One 15-* code with monthly actual increments; revised budget 4,000,000."""
    months = [("2025-11", increments[0]), ("2025-12", increments[1]),
              ("2026-01", increments[2]), ("2026-02", increments[3])]
    return {"1000.15-01-426.MAT": {
        "cost_code": "15-01-426", "budget_amounts": {"revised_budget": "4000000.00"},
        "actuals": {"monthly_actuals": [{"month": m, "amount_decimal_string": str(v)} for m, v in months]}}}


MAP = {"20-18-110": {"budget_code_key": "1000.20-18-110.OVH"}}


def test_confirmed_when_fee_tracks_progress_with_stable_total():
    rows = _fee_rows([("2025-11", 1000000), ("2025-12", 800000),
                      ("2026-01", 600000), ("2026-02", 400000)])
    ctx = _cow_context([2000000, 400000, 400000, 400000])  # pct 0.50,0.60,0.70,0.80
    inputs = {"history_rows": rows, "context_by": ctx}
    audit = gp.build_audit(inputs, MAP, "tropical")
    assert audit["overall_status"] == "confirmed"
    f = audit["per_fee"][0]
    assert f["inverse_relationship_with_progress"] is True
    assert f["implied_total_stable"] is True


def test_unsupported_when_fee_flat_against_progress():
    rows = _fee_rows([("2025-11", 500000), ("2025-12", 500000),
                      ("2026-01", 500000), ("2026-02", 500000)])
    ctx = _cow_context([2000000, 400000, 400000, 400000])
    inputs = {"history_rows": rows, "context_by": ctx}
    audit = gp.build_audit(inputs, MAP, "tropical")
    assert audit["per_fee"][0]["proportionality_status"] == "unsupported"
    assert audit["overall_status"] != "confirmed"


def test_insufficient_evidence_without_cost_of_work():
    rows = _fee_rows([("2025-11", 1000000), ("2025-12", 800000)])
    inputs = {"history_rows": rows, "context_by": {}}   # no 15-* progress
    audit = gp.build_audit(inputs, MAP, "tropical")
    assert audit["per_fee"][0]["proportionality_status"] == "insufficient_evidence"
