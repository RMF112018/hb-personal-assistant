from construction_financial_review.common.budget_keys import (
    parse_budget_key, cost_code_family, build_budget_key, is_valid_category, VALID_CATEGORIES,
)


def test_parse_valid_key():
    assert parse_budget_key("1000.15-16-110.SUB") == ("1000", "15-16-110", "SUB")


def test_parse_handles_multi_dash_cost_code():
    sub, cc, cat = parse_budget_key("0000.03-01-413.LBN")
    assert sub == "0000" and cc == "03-01-413" and cat == "LBN"


def test_parse_rejects_malformed():
    assert parse_budget_key("1000.15-16-110") is None
    assert parse_budget_key("") is None
    assert parse_budget_key(None) is None
    assert parse_budget_key("a.b.c.d") is None


def test_cost_code_family():
    assert cost_code_family("15-16-110") == "15-16"
    assert cost_code_family("15-01-XXX") == "15-01"
    assert cost_code_family("20-18-105") == "20-18"
    assert cost_code_family(None) is None


def test_build_and_category():
    assert build_budget_key("1000", "15-16-110", "SUB") == "1000.15-16-110.SUB"
    assert is_valid_category("SUB") and is_valid_category("LBN")
    assert not is_valid_category("ZZZ")
    assert set(VALID_CATEGORIES) == {"SUB", "MAT", "LAB", "LBN", "OVH"}
