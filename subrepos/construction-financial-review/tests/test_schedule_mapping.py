"""Schedule cost-code -> budget_code_key mapping: canonical authority, ambiguity, no fuzzy."""
from construction_financial_review.schedule_analysis import schedule_mapping as sm
from construction_financial_review.schedule_analysis import schedule_io

CANONICAL = [
    {"budget_code_key": "1000.15-02-010.SUB", "cost_code": "15-02-010", "category": "SUB"},
    {"budget_code_key": "1000.15-16-110.SUB", "cost_code": "15-16-110", "category": "SUB"},
    {"budget_code_key": "1000.15-16-110.MAT", "cost_code": "15-16-110", "category": "MAT"},
    {"budget_code_key": "1000.99-99-999.SUB", "cost_code": "99-99-999", "category": "SUB"},
]


def _activity(cost_code=None, cost_code_raw=None, candidates=None, conf=None, **over):
    a = {
        "activity_id": over.get("activity_id", "A-1"),
        "activity_object_id": over.get("activity_object_id", 1),
        "activity_name": over.get("activity_name", "Test"),
        "activity_codes": {
            "cost_code": cost_code,
            "cost_code_raw": cost_code_raw,
            "candidate_budget_code_keys": candidates or [],
            "budget_code_mapping_confidence": conf,
        },
    }
    return a


def test_unique_cost_code_maps_high():
    idx = sm.build_canonical_index(CANONICAL)
    d = sm.resolve_activity(_activity(cost_code="15-02-010"), idx)
    assert d["mapping_status"] == sm.STATUS_MAPPED
    assert d["mapped_budget_code_key"] == "1000.15-02-010.SUB"
    assert d["mapping_method"] == sm.METHOD_CC_UNIQUE
    assert d["mapping_confidence"] == "high"


def test_multi_category_cost_code_is_ambiguous_not_forced():
    """15-16-110 spans .MAT and .SUB. Even with an extractor candidate, it stays ambiguous."""
    idx = sm.build_canonical_index(CANONICAL)
    d = sm.resolve_activity(
        _activity(cost_code="15-16-110", candidates=["1000.15-16-110.SUB"], conf="medium"), idx)
    assert d["mapping_status"] == sm.STATUS_AMBIGUOUS
    assert d["mapped_budget_code_key"] is None            # never force .SUB
    assert sorted(d["candidate_budget_code_keys"]) == ["1000.15-16-110.MAT", "1000.15-16-110.SUB"]
    assert d["requires_human_review"] is True
    # extractor candidate is recorded only as supporting evidence
    assert d["extractor_candidate_budget_code_keys"] == ["1000.15-16-110.SUB"]


def test_cost_code_not_in_canonical_is_invalid():
    idx = sm.build_canonical_index(CANONICAL)
    d = sm.resolve_activity(_activity(cost_code="77-77-777"), idx)
    assert d["mapping_status"] == sm.STATUS_INVALID
    assert d["mapped_budget_code_key"] is None
    assert d["requires_human_review"] is True


def test_no_cost_code_is_not_applicable():
    idx = sm.build_canonical_index(CANONICAL)
    d = sm.resolve_activity(_activity(), idx)
    assert d["mapping_status"] == sm.STATUS_NA
    assert d["mapped_budget_code_key"] is None


def test_raw_cost_code_normalized_then_mapped():
    idx = sm.build_canonical_index(CANONICAL)
    d = sm.resolve_activity(_activity(cost_code_raw=1502010), idx)
    assert d["schedule_cost_code"] == "15-02-010"
    assert d["mapped_budget_code_key"] == "1000.15-02-010.SUB"


def test_normalize_cost_code_padding():
    assert schedule_io.normalize_cost_code(1502010) == "15-02-010"
    assert schedule_io.normalize_cost_code("1516110") == "15-16-110"
    assert schedule_io.normalize_cost_code("15-16-110") == "15-16-110"
    assert schedule_io.normalize_cost_code(None) is None
    assert schedule_io.normalize_cost_code("") is None


def test_aggregate_crosswalk_groups_and_sorts():
    idx = sm.build_canonical_index(CANONICAL)
    acts = [
        _activity(cost_code="15-02-010", activity_id="A-1", activity_object_id=1),
        _activity(cost_code="15-02-010", activity_id="A-2", activity_object_id=2),
        _activity(cost_code="15-16-110", activity_id="A-3", activity_object_id=3),
    ]
    decisions = sm.map_activities(acts, idx)
    rows = sm.aggregate_crosswalk(decisions)
    mapped = [r for r in rows if r["mapping_status"] == sm.STATUS_MAPPED][0]
    assert mapped["activity_count"] == 2
    assert mapped["activity_ids"] == ["A-1", "A-2"]
    assert any(r["mapping_status"] == sm.STATUS_AMBIGUOUS for r in rows)
    assert rows == sorted(rows, key=lambda r: (r["schedule_cost_code"] or "", r["mapping_status"],
                                               r.get("mapped_budget_code_key") or ""))
