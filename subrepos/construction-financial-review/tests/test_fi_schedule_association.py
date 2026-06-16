"""Schedule association: direct needs a deterministic link; project_level is context only."""
from construction_financial_review.forecast_intelligence import schedule_association as sa

ROLLUP = {
    "1000.15-16-110.SUB": {  # direct: mapped + open work
        "schedule_mapping_status": "mapped", "mapped_activity_count": 4, "open_activity_count": 3,
        "remaining_duration_days": "100.00", "latest_remaining_finish": "2026-08-01",
        "schedule_remaining_work_status": "material_remaining_work",
        "completed_activity_count": 1,
    },
    "1000.15-16-200.SUB": {  # ambiguous mapping, no direct link
        "schedule_mapping_status": "ambiguous", "mapped_activity_count": 0, "open_activity_count": 0,
        "remaining_duration_days": "0.00", "latest_remaining_finish": None,
        "schedule_remaining_work_status": "unmapped_or_ambiguous", "completed_activity_count": 0,
    },
}

META = {
    "1000.15-16-110.SUB": {"cost_code": "15-16-110", "family": "15-16", "division": "15",
                           "owner_sov_code": "OWN-1", "revised_budget": "1000000"},
    "1000.15-16-110.MAT": {"cost_code": "15-16-110", "family": "15-16", "division": "15",
                           "owner_sov_code": "OWN-1", "revised_budget": "500000"},
    "1000.15-16-200.SUB": {"cost_code": "15-16-200", "family": "15-16", "division": "15",
                           "owner_sov_code": "OWN-1", "revised_budget": "200000"},
    "1000.99-99-999.OVH": {"cost_code": "99-99-999", "family": "99-99", "division": "99",
                           "owner_sov_code": "OWN-9", "revised_budget": "10000"},
}

DIRECT_IDS = {"1000.15-16-110.SUB": ["A-1", "A-2", "A-3"]}


def _indices():
    return sa.build_group_indices(ROLLUP, META)


def test_direct_requires_deterministic_mapped_link():
    idx = _indices()
    r = sa.classify("1000.15-16-110.SUB", META["1000.15-16-110.SUB"], ROLLUP, DIRECT_IDS, idx,
                    True, "tropical")
    assert r["schedule_association"] == "direct"
    assert r["direct_mapped_activity_count"] == 3
    assert r["activity_refs"] == ["A-1", "A-2", "A-3"]
    assert r["schedule_confidence"] == "1.0"
    assert r["influences_code_estimate"] is True


def test_ambiguous_never_direct():
    idx = _indices()
    r = sa.classify("1000.15-16-200.SUB", META["1000.15-16-200.SUB"], ROLLUP, {}, idx, True, "tropical")
    assert r["schedule_association"] != "direct"
    # shares family 15-16 (which has direct work) -> cost_code_family
    assert r["schedule_association"] == "cost_code_family"
    assert r["schedule_confidence"] == "0.6"


def test_family_borrow_prorated_and_influences():
    idx = _indices()
    r = sa.classify("1000.15-16-110.MAT", META["1000.15-16-110.MAT"], ROLLUP, {}, idx, True, "tropical")
    assert r["schedule_association"] == "cost_code_family"
    assert r["influences_code_estimate"] is True
    assert float(r["remaining_duration_days"]) > 0    # borrowed a prorated share


def test_project_level_is_context_only():
    idx = _indices()
    r = sa.classify("1000.99-99-999.OVH", META["1000.99-99-999.OVH"], ROLLUP, {}, idx, True, "tropical")
    assert r["schedule_association"] == "project_level"
    assert r["schedule_confidence"] == "0.0"
    assert r["influences_code_estimate"] is False      # never drives a code-level estimate


def test_none_when_no_project_work():
    idx = _indices()
    r = sa.classify("1000.99-99-999.OVH", META["1000.99-99-999.OVH"], ROLLUP, {}, idx, False, "tropical")
    assert r["schedule_association"] == "none"
    assert r["influences_code_estimate"] is False
