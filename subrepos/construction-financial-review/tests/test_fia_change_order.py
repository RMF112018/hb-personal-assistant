"""Priority 7 change-order exposure tests."""
from construction_financial_review.forecast_improvement_audit import change_order

from tests._fia_fixtures import minimal_inputs


def test_classify_mapping():
    assert change_order.classify("approved", 1) == "approved_executed"
    assert change_order.classify("approved", 0) == "pending_unsigned"
    assert change_order.classify("pending", 0) == "potential_unapproved"
    assert change_order.classify("draft", 0) == "potential_unapproved"
    assert change_order.classify("void", 0) == "void_rejected"
    assert change_order.classify("something_else", 0) == "unknown_status"


def _co(rk, status, executed, total):
    return {"record_key": rk, "change_order_family": "fam", "contract_record_key": "c1",
            "number": rk, "status": status, "executed": executed, "paid": 0,
            "grand_total": total, "schedule_impact_amount": "0", "due_date": None}


def test_build_classes_double_count_and_gaps():
    db = {"db_present": True, "contracts": [], "change_orders": [
        _co("co-approved", "approved", 1, "100000"),
        _co("co-pending", "pending", 0, "50000"),
        _co("co-void", "void", 0, "-2000"),
        _co("co-weird", "mystery", 0, "1"),
    ]}
    rows, summary, gaps = change_order.build(minimal_inputs(db=db), {})
    by = {r["change_order_record_key"]: r for r in rows}
    assert by["co-approved"]["exposure_class"] == "approved_executed"
    assert by["co-approved"]["double_count_risk_vs_current_projected_cost"] is True
    assert by["co-approved"]["is_committed"] is True
    assert by["co-pending"]["exposure_class"] == "potential_unapproved"
    assert by["co-pending"]["double_count_risk_vs_current_projected_cost"] is False
    assert by["co-pending"]["is_actual_cost"] is False
    assert by["co-void"]["exposure_class"] == "void_rejected"
    assert summary["change_order_count"] == 4
    assert any(g["gap_type"] == "no_budget_code_mapping" for g in gaps)
    assert any(g["gap_type"] == "unknown_change_order_status" for g in gaps)
    assert all(r["mapping_confidence"] == "none" for r in rows)
    assert all(r["requires_human_acceptance"] is True for r in rows)


def test_build_db_absent():
    rows, summary, gaps = change_order.build(minimal_inputs(db={"db_present": False}), {})
    assert rows == []
    assert summary["db_present"] is False
    assert any(g["gap_type"] == "sqlite_db_absent" for g in gaps)
