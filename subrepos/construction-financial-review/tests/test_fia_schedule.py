"""Priority 5 schedule cost-loading readiness tests."""
from construction_financial_review.forecast_improvement_audit import schedule_readiness

from tests._fia_fixtures import budget_entry, minimal_inputs

BK = {"1000.15-03-100.SUB": budget_entry("1000.15-03-100.SUB", "15-03-100", "x")}


def _activity(conf="none", cands=None, dates=True, pct=0.5, logic=True, labor_cost=0):
    return {
        "data_date": "2026-06-01",
        "budget_code_mapping_confidence": conf,
        "candidate_budget_code_keys": cands or [],
        "dates": {"start": "2026-01-01", "finish": "2026-02-01"} if dates else {},
        "progress": {"activity_percent_complete": pct},
        "predecessors": [1] if logic else [], "successors": [2] if logic else [],
        "raw_xml_fields": {"PlannedLaborCost": labor_cost},
        "forecast_relevance": {"is_active_work": True, "is_cost_mappable": True},
    }


def test_can_drive_when_mapped_and_cost_loaded():
    acts = [_activity(conf="high", cands=["1000.15-03-100.SUB"], labor_cost=1000) for _ in range(5)]
    audit, _ = schedule_readiness.build(minimal_inputs(schedule_activities=acts, budget_by_key=BK), {})
    assert audit["recommended_posture"] == "schedule_can_drive_phasing"
    assert audit["cost_loading_presence_fraction"] == 1.0


def test_context_only_when_unmapped_but_dated():
    acts = [_activity(conf="none", labor_cost=0) for _ in range(5)]
    audit, gaps = schedule_readiness.build(minimal_inputs(schedule_activities=acts, budget_by_key=BK), {})
    assert audit["recommended_posture"] == "schedule_context_only"
    assert any(g["gap_type"] == "schedule_not_cost_loaded" for g in gaps)


def test_not_usable_when_no_dates_no_mapping():
    acts = [_activity(conf="none", dates=False, labor_cost=0) for _ in range(5)]
    audit, _ = schedule_readiness.build(minimal_inputs(schedule_activities=acts, budget_by_key=BK), {})
    assert audit["recommended_posture"] == "schedule_not_usable"


def test_inform_only_when_partially_mapped():
    acts = [_activity(conf="high", cands=["1000.15-03-100.SUB"], labor_cost=0) for _ in range(2)]
    acts += [_activity(conf="none", labor_cost=0) for _ in range(3)]
    audit, _ = schedule_readiness.build(minimal_inputs(schedule_activities=acts, budget_by_key=BK), {})
    assert audit["recommended_posture"] == "schedule_can_inform_phasing_only"


def test_absent_schedule_gap():
    audit, gaps = schedule_readiness.build(minimal_inputs(schedule_activities=[]), {})
    assert audit["recommended_posture"] == "schedule_not_usable"
    assert any(g["gap_type"] == "schedule_package_absent" for g in gaps)
