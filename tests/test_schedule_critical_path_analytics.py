"""Unit tests for XER source critical path analytics."""

from __future__ import annotations

from hb_assistant.construction.analytics.schedule_critical_path_analytics import (
    METRIC_STATUS_AVAILABLE_XER_DRIVING,
    METRIC_STATUS_AVAILABLE_XER_TOTFLOAT,
    SOURCE_CRITICAL_BASIS_XER_DRIVING,
    SOURCE_CRITICAL_BASIS_XER_TOTFLOAT,
    classify_xer_critical_activities,
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