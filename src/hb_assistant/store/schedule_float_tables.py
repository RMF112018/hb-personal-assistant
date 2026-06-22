"""V65 schedule derived finish-float columns (additive ALTER)."""

from __future__ import annotations

V65_IMPORT_ALTER_COLUMNS: tuple[str, ...] = (
    "compute_total_float_type",
    "critical_activity_path_type",
    "critical_activity_float_threshold",
    "calculate_float_based_on_finish_date",
)

METRIC_STATUS_CHECK_VALUES: tuple[str, ...] = (
    "measured",
    "passed_threshold",
    "warning_threshold",
    "failed_threshold",
    "not_measurable_missing_data",
    "not_applicable",
    "measured_from_derived_finish_float",
    "partially_measurable_critical_float_available",
    "not_measurable_missing_longest_path_data",
    "not_measurable_requires_recalculation",
    "measured_from_xer_driving_path",
    "measured_from_msp_critical_flag",
    "measured_from_explicit_source_float",
)

V65_ACTIVITY_ALTER_COLUMNS: tuple[str, ...] = (
    "remaining_early_start",
    "remaining_early_finish",
    "remaining_late_start",
    "remaining_late_finish",
    "derived_total_float_hours",
    "derived_total_float_days",
    "derived_float_basis",
    "derived_is_critical_by_float_threshold",
)