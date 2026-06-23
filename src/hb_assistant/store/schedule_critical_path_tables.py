"""V67 schedule source-aware critical path columns (additive ALTER)."""

from __future__ import annotations

V67_IMPORT_ALTER_COLUMNS: tuple[str, ...] = (
    "critical_path_type",
    "critical_float_threshold",
    "schedule_options_json",
    "baseline_source",
)

V67_ACTIVITY_ALTER_COLUMNS: tuple[str, ...] = (
    "explicit_total_float_hours",
    "explicit_total_float_days",
    "explicit_free_float_hours",
    "explicit_free_float_days",
    "float_source",
    "source_critical_flag",
    "source_driving_path_flag",
    "source_longest_path_flag",
    "float_path",
    "float_path_order",
    "critical_path_number",
    "critical_path_source",
    "target_start",
    "target_finish",
    "target_duration",
    "baseline_start",
    "baseline_finish",
    "baseline_duration",
)

V67_METRIC_STATUS_ADDITIONS: tuple[str, ...] = (
    "measured_from_xer_driving_path",
    "measured_from_msp_critical_flag",
    "measured_from_explicit_source_float",
)

FLOAT_SOURCE_VALUES: tuple[str, ...] = (
    "xer_explicit",
    "msp_explicit",
    "p6_derived_finish",
    "missing",
)

CRITICAL_PATH_SOURCE_VALUES: tuple[str, ...] = (
    "xer_driving_path_flag",
    "xer_total_float_threshold",
    "msp_critical_flag",
    "p6_derived_float_only",
    "app_cpm_recalculated",
    "missing",
)

BASELINE_SOURCE_VALUES: tuple[str, ...] = (
    "xer_project",
    "msp_baseline",
    "missing",
)

SOURCE_FORMAT_MS_PROJECT_XML = "ms_project_xml"