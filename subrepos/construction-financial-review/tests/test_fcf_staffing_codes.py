"""Staffing code recognition + policy census + no fabricated staff-change events."""
from construction_financial_review.forecast_cost_frequency import staffing_codes as sc

CFG = {"weekly_internal_staffing_budget_code_keys": ["1000.10-01-302.LAB", "0000.03-01-413.LAB"]}


def test_is_internal_staffing_code():
    assert sc.is_internal_staffing_code("1000.10-01-302.LAB", CFG)
    assert not sc.is_internal_staffing_code("0000.03-01-025.MAT", CFG)


def test_policy_audit_found_and_missing():
    audit = sc.policy_audit(CFG, {"1000.10-01-302.LAB"}, "tropical")
    assert audit["found_in_canonical_budget_details"] == ["1000.10-01-302.LAB"]
    assert audit["missing_from_canonical_budget_details"] == ["0000.03-01-413.LAB"]
    assert audit["all_configured_present"] is False


def test_no_fabricated_staff_change_events():
    assert sc.staff_change_events(CFG) == []
    assert sc.staff_change_events({"staff_change_events": [
        {"effective_date": "2026-10-01", "budget_code_key": "K", "action": "remove", "note": "x"}]}) == [
        {"effective_date": "2026-10-01", "budget_code_key": "K", "action": "remove", "note": "x"}]
