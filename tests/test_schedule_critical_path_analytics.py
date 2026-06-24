"""Unit tests for XER source critical path analytics."""

from __future__ import annotations

from hb_assistant.construction.analytics.schedule_critical_path_analytics import (
    METRIC_STATUS_AVAILABLE_XER_DRIVING,
    METRIC_STATUS_AVAILABLE_XER_TOTFLOAT,
    SOURCE_CRITICAL_BASIS_XER_DRIVING,
    SOURCE_CRITICAL_BASIS_XER_TOTFLOAT,
    classify_xer_critical_activities,
    compute_msp_critical_slack_analytics,
    compute_source_critical_path_analytics,
    resolve_xer_critical_basis,
)


def test_resolve_xer_critical_basis_variants() -> None:
    assert resolve_xer_critical_basis("CT_DrivPath") == SOURCE_CRITICAL_BASIS_XER_DRIVING
    assert resolve_xer_critical_basis("CP_Drtn") == SOURCE_CRITICAL_BASIS_XER_DRIVING
    assert resolve_xer_critical_basis("CT_TotFloat") == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT


def test_classify_totfloat_marks_critical_by_threshold() -> None:
    activities = [
        {
            "source_driving_path_flag": 1,
            "explicit_total_float_hours": "-8",
        },
        {
            "source_driving_path_flag": 0,
            "explicit_total_float_hours": "16",
        },
        {
            "source_driving_path_flag": 1,
            "explicit_total_float_hours": None,
        },
    ]
    basis = classify_xer_critical_activities(
        activities,
        critical_path_type="CT_TotFloat",
        threshold_hours="0",
    )
    assert basis == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT
    assert activities[0]["source_critical_flag"] == 1
    assert activities[0]["critical_path_source"] == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT
    assert activities[1]["source_critical_flag"] == 0
    assert activities[2]["source_critical_flag"] == 0
    assert activities[2]["critical_path_source"] == SOURCE_CRITICAL_BASIS_XER_DRIVING


def test_compute_analytics_drivpath() -> None:
    activities = [
        {"source_driving_path_flag": 1, "explicit_total_float_hours": "0", "source_critical_flag": 1},
        {"source_driving_path_flag": 0, "explicit_total_float_hours": "8", "source_critical_flag": 0},
    ]
    analytics = compute_source_critical_path_analytics(
        {"critical_path_type": "CT_DrivPath", "critical_float_threshold": "0"},
        activities,
    )
    assert analytics["source_critical_basis"] == SOURCE_CRITICAL_BASIS_XER_DRIVING
    assert analytics["source_critical_activity_count"] == 1
    assert analytics["source_driving_path_count"] == 1
    assert analytics["status"] == METRIC_STATUS_AVAILABLE_XER_DRIVING


def test_compute_analytics_totfloat() -> None:
    activities = [
        {
            "source_driving_path_flag": 1,
            "explicit_total_float_hours": "-1",
            "source_critical_flag": 1,
            "critical_path_source": SOURCE_CRITICAL_BASIS_XER_TOTFLOAT,
        },
        {
            "source_driving_path_flag": 1,
            "explicit_total_float_hours": None,
            "source_critical_flag": 0,
            "critical_path_source": SOURCE_CRITICAL_BASIS_XER_DRIVING,
        },
    ]
    analytics = compute_source_critical_path_analytics(
        {"critical_path_type": "CT_TotFloat", "critical_float_threshold": "0"},
        activities,
    )
    assert analytics["source_critical_basis"] == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT
    assert analytics["source_critical_activity_count"] == 1
    assert analytics["explicit_float_activity_count"] == 1
    assert analytics["driving_path_with_explicit_float_count"] == 1
    assert analytics["status"] == METRIC_STATUS_AVAILABLE_XER_TOTFLOAT


def test_compute_msp_critical_slack_analytics_counts_consistency_and_exclusions() -> None:
    analytics = compute_msp_critical_slack_analytics(
        [
            {
                "activity_id": "C0",
                "activity_name": "Critical zero slack",
                "source_critical_flag": 1,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "0.0",
                "explicit_free_float_days": "0.0",
            },
            {
                "activity_id": "CN",
                "activity_name": "Critical negative slack",
                "source_critical_flag": 1,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "-0.5",
            },
            {
                "activity_id": "CP",
                "activity_name": "Critical positive slack",
                "source_critical_flag": 1,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "2.0",
            },
            {
                "activity_id": "FN",
                "activity_name": "False negative slack",
                "source_critical_flag": 0,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "-1.0",
            },
            {
                "activity_id": "FP",
                "activity_name": "False positive slack",
                "source_critical_flag": 0,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "1.0",
            },
            {
                "activity_id": "MS",
                "activity_name": "Milestone excluded",
                "source_critical_flag": 1,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "0.0",
                "is_milestone": True,
            },
            {
                "activity_id": "MISSING",
                "activity_name": "Missing critical but slack present",
                "source_critical_flag": 0,
                "source_critical_flag_present": False,
                "explicit_total_float_days": "1.0",
            },
        ]
    )

    assert analytics["source_format"] == "ms_project_xml"
    assert analytics["total_activity_count"] == 7
    assert analytics["eligible_activity_count"] == 6
    assert analytics["excluded_activity_count"] == 1
    assert analytics["exclusion_reasons"]["milestone"] == 1
    assert analytics["eligible_evidence_activity_count"] == 6
    assert analytics["critical_true_count"] == 3
    assert analytics["critical_false_count"] == 2
    assert analytics["critical_missing_count"] == 1
    assert analytics["total_slack_present_count"] == 6
    assert analytics["free_slack_present_count"] == 1
    assert analytics["critical_true_nonpositive_slack_count"] == 2
    assert analytics["critical_true_positive_slack_count"] == 1
    assert analytics["critical_false_negative_slack_count"] == 1
    assert analytics["consistent_critical_slack_count"] == 3
    assert analytics["inconsistent_critical_slack_count"] == 2
    assert analytics["consistency_ratio"] == 0.5
    assert analytics["not_a_dcma_critical_path_test"] is True
    assert analytics["source_export_only"] is True
    assert analytics["cpm_recalculation_performed"] is False
    statuses = {sample["consistency_status"] for sample in analytics["inconsistency_samples"]}
    assert "critical_true_positive_slack" in statuses
    assert "critical_false_negative_slack" in statuses
    assert "indeterminate_missing_critical_or_total_slack" in statuses
