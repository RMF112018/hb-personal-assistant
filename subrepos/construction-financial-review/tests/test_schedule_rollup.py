"""Per-budget-code rollup: remaining-work classification and zero-vs-negative-float separation."""
from construction_financial_review.schedule_analysis import schedule_mapping as sm
from construction_financial_review.schedule_analysis import schedule_rollup as sr

CANONICAL = [
    {"budget_code_key": "1000.15-02-010.SUB", "sub_job": "1000", "cost_code": "15-02-010",
     "category": "SUB", "budget_code_description": "Test SUB"},
]


def _activity(objid, status="In Progress", total_float=None, remaining_days=2.0,
              rem_start="2026-06-01T08:00:00", rem_finish="2026-06-10T16:00:00"):
    return {
        "activity_id": f"A-{objid}",
        "activity_object_id": objid,
        "activity_name": f"Act {objid}",
        "activity_type": "Task Dependent",
        "status": status,
        "wbs_code": 1, "wbs_name": "WBS",
        "dates": {"start": "2026-05-01T08:00:00", "finish": "2026-06-10T16:00:00",
                  "actual_start": "2026-05-01T08:00:00", "actual_finish": None,
                  "remaining_early_start": rem_start, "remaining_early_finish": rem_finish},
        "durations": {"original_duration_days_8h": 10.0, "remaining_duration_days_8h": remaining_days},
        "progress": {"activity_percent_complete": 0.5, "duration_percent_complete": 0.5,
                     "physical_percent_complete": 0.0},
        "float": {"total_float_days_8h": total_float, "free_float_days_8h": 0.0},
        "constraints": {"primary_constraint_type": None, "primary_constraint_date": None},
        "activity_codes": {"cost_code": "15-02-010", "cost_code_raw": 1502010,
                           "candidate_budget_code_keys": [], "budget_code_mapping_confidence": None},
        "predecessors": [], "successors": [],
    }


def _rollup(activities):
    idx = sm.build_canonical_index(CANONICAL)
    decisions = sm.map_activities(activities, idx)
    by_objid = {d["activity_object_id"]: d for d in decisions}
    features = sr.build_activity_features(activities, by_objid)
    rows = sr.build_budget_rollup(CANONICAL, features, "tropical")
    return rows[0]


def test_material_by_open_count():
    r = _rollup([_activity(1), _activity(2), _activity(3)])  # 3 open >= threshold
    assert r["open_activity_count"] == 3
    assert r["schedule_remaining_work_status"] == sr.RW_MATERIAL


def test_minor_remaining_work():
    r = _rollup([_activity(1, remaining_days=3.0)])  # 1 open, < 14 days
    assert r["schedule_remaining_work_status"] == sr.RW_MINOR
    assert r["schedule_risk_level"] == sr.RISK_LOW


def test_material_by_duration():
    r = _rollup([_activity(1, remaining_days=20.0)])  # 1 open but >= 14 days
    assert r["schedule_remaining_work_status"] == sr.RW_MATERIAL


def test_zero_float_does_not_escalate_above_medium():
    """total_float == 0 is a critical-path proxy but must NOT escalate risk like negative float."""
    r = _rollup([_activity(1, total_float=0.0), _activity(2, total_float=0.0),
                 _activity(3, total_float=0.0)])
    assert r["negative_float_activity_count"] == 0
    assert r["critical_or_longest_path_activity_count"] == 3   # proxy still counts zero float
    assert r["schedule_risk_level"] == sr.RISK_MEDIUM          # not high


def test_negative_float_escalates_to_high():
    r = _rollup([_activity(1, total_float=-5.0), _activity(2, total_float=-5.0),
                 _activity(3, total_float=-5.0)])
    assert r["negative_float_activity_count"] == 3
    assert r["schedule_risk_level"] == sr.RISK_HIGH
    assert "negative_float_remaining_work" in r["schedule_risk_flags"]


def test_completed_only_is_complete_status():
    r = _rollup([_activity(1, status="Completed"), _activity(2, status="Completed")])
    assert r["open_activity_count"] == 0
    assert r["schedule_remaining_work_status"] == sr.RW_COMPLETE
    assert r["schedule_risk_level"] == sr.RISK_NONE


def test_no_schedule_evidence():
    r = _rollup([])
    assert r["schedule_remaining_work_status"] == sr.RW_NONE
    assert r["schedule_mapping_status"] == "none"
