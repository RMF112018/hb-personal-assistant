"""Mapping: unique / multi-category rollup / family / unmapped; duplicate-code; 10-XX; presence."""
from construction_financial_review.forecast_history_informed import history_mapping
from construction_financial_review.schedule_analysis.schedule_mapping import build_canonical_index

BUDGET_CODES = [
    {"budget_code_key": "1000.15-16-110.MAT", "cost_code": "15-16-110", "category": "MAT"},
    {"budget_code_key": "1000.15-16-110.SUB", "cost_code": "15-16-110", "category": "SUB"},
    {"budget_code_key": "0000.03-01-025.MAT", "cost_code": "03-01-025", "category": "MAT"},
    {"budget_code_key": "1000.20-18-110.OVH", "cost_code": "20-18-110", "category": "OVH"},
    {"budget_code_key": "1000.15-01-426.MAT", "cost_code": "15-01-426", "category": "MAT"},
]
INDEX = build_canonical_index(BUDGET_CODES)


def _row(cc, desc="X", pkg="cash_flow", sheet="s", row=1):
    return {"history_source_package": pkg, "source_workbook": "W", "source_sheet": sheet,
            "source_row": row, "cost_code": cc, "description": desc}


def test_unique_match():
    m = history_mapping.map_cost_code("20-18-110", [_row("20-18-110", "CONTRACTORS FEE")], INDEX)
    assert m["mapping_status"] == "cost_code_unique_budget_match"
    assert m["budget_code_key"] == "1000.20-18-110.OVH"
    assert m["mapping_confidence"] == 1.0


def test_multi_category_rollup_not_forced():
    m = history_mapping.map_cost_code("15-16-110", [_row("15-16-110")], INDEX)
    assert m["mapping_status"] == "cost_code_multi_category_rollup"
    assert m["budget_code_key"] is None
    assert set(m["candidate_budget_code_keys"]) == {"1000.15-16-110.MAT", "1000.15-16-110.SUB"}


def test_family_rollup_when_code_absent_but_family_present():
    m = history_mapping.map_cost_code("15-01-999", [_row("15-01-999")], INDEX)
    assert m["mapping_status"] == "cost_code_family_rollup"
    assert "1000.15-01-426.MAT" in m["candidate_budget_code_keys"]


def test_unmapped_absent():
    m = history_mapping.map_cost_code("99-99-999", [_row("99-99-999")], INDEX)
    assert m["mapping_status"] == "unmapped_absent_from_budget_details"
    assert m["budget_code_key"] is None
    assert m["mapping_confidence"] == 0.0


def test_duplicate_cost_code_warning():
    rows = [_row("20-18-107", "SUBCONTRACTOR DEFAULT INSURANCE", row=1),
            _row("20-18-107", "PAYMENT & PERFORMANCE BOND", row=2)]
    m = history_mapping.map_cost_code("20-18-107", rows, INDEX)
    assert m["duplicate_cost_code_warning"] is True
    assert len(m["duplicate_lineage"]) == 2


def test_10xx_description_sensitive():
    rows = [_row("10-01-025", "GENERAL REQUIREMENTS"), _row("10-01-025", "Plans/Printing")]
    m = history_mapping.map_cost_code("10-01-025", rows, INDEX)
    assert m["description_sensitive_review"] is True


def test_check_code_presence_absent_everywhere():
    rows = [_row("20-18-110")]
    pr = history_mapping.check_code_presence("15-16-100", rows, INDEX, set(INDEX["keys"]))
    assert pr["absent_everywhere"] is True
    assert pr["present_in_canonical_budget_details"] is False
    assert "canonical_budget_details" in pr["sources_checked"]
