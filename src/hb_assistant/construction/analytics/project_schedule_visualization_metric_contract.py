"""Project Schedule Hub visualization metric formula contracts.

Phase 5 is intentionally contract-only.  This module defines future visualization
metric formulas, source mappings, readiness, caveats, and payload guidance without
performing chart aggregation or adding API routes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Literal

from hb_assistant.store.connection import open_connection

ReadinessStatus = Literal[
    "ready_now",
    "ready_after_api_contract",
    "ready_after_cpm_reconciliation",
    "ready_after_udf_normalization",
    "ready_after_baseline_selection",
    "ready_after_trend_aggregation",
    "ready_after_cost_loading_validation",
    "deferred",
]

BasisLabel = Literal[
    "source_export",
    "computed_cpm",
    "baseline",
    "selected_baseline",
    "prior_update",
    "current_update",
    "udf_derived",
    "quality_derived",
    "diff_derived",
]

APPROVED_READINESS_STATUSES: tuple[ReadinessStatus, ...] = (
    "ready_now",
    "ready_after_api_contract",
    "ready_after_cpm_reconciliation",
    "ready_after_udf_normalization",
    "ready_after_baseline_selection",
    "ready_after_trend_aggregation",
    "ready_after_cost_loading_validation",
    "deferred",
)

APPROVED_BASIS_LABELS: tuple[BasisLabel, ...] = (
    "source_export",
    "computed_cpm",
    "baseline",
    "selected_baseline",
    "prior_update",
    "current_update",
    "udf_derived",
    "quality_derived",
    "diff_derived",
)

REQUIRED_METRIC_KEYS: tuple[str, ...] = (
    "monthly_activity_start_finish_distribution",
    "planned_vs_actual_percent_complete",
    "schedule_performance_ratio",
    "schedule_delay_over_time",
    "schedule_changes_over_time",
    "delay_analysis",
    "window_start_accuracy",
    "window_finish_accuracy",
    "should_have_finished_status",
    "schedule_compression_ratio",
    "project_schedule_health_index",
    "schedule_feasibility_score",
    "required_recovery_days",
    "critical_path_length_index",
    "total_float_consumption_index",
    "critical_issues_category_model",
)

REQUIRED_NAMED_UDFS: tuple[str, ...] = (
    "OLD ID",
    "PHASE",
    "FLOOR",
    "SECTOR / AREA",
    "SUBCONTRACTOR",
    "Cost Code",
    "Filter Out",
    "Start (Previous Status)",
    "Start Previous Status",
    "Finish (Previous Status)",
    "Finish Previous Status",
    "Update Notes - 1",
    "Update Notes - 2",
    "Update Notes",
    "Schedule Review Comments",
)

NON_CAUSATION_CAVEAT = (
    "This metric is a schedule review cue only; it is not a causation, entitlement, "
    "responsibility, or compensability finding."
)


@dataclass(frozen=True)
class VisualizationMetricContract:
    metric_key: str
    display_name: str
    category: str
    pm_facing_purpose: str
    formula_summary: str
    formula_detail: str
    source_tables: tuple[str, ...]
    source_columns: dict[str, tuple[str, ...]]
    udf_dependencies: tuple[str, ...]
    comparison_basis: tuple[str, ...]
    weighting_basis: tuple[str, ...]
    default_weighting_basis: str
    configurable_thresholds: dict[str, Any]
    configurable_weights: dict[str, float]
    readiness_status: ReadinessStatus
    blockers: tuple[str, ...]
    caveats: tuple[str, ...]
    future_api_payload_shape: dict[str, Any]
    required_tests: tuple[str, ...]
    notes: tuple[str, ...]
    basis_labels: tuple[BasisLabel, ...]
    display_aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _shape(*fields: str) -> dict[str, Any]:
    return {"type": "object", "fields": list(fields)}


def _current_activity_columns(*extra: str) -> dict[str, tuple[str, ...]]:
    return {
        "procore_ep_schedule_activities": (
            "schedule_version_key",
            "activity_id",
            "activity_name",
            "activity_status",
            "planned_start",
            "planned_finish",
            "start_date",
            "finish_date",
            "early_start",
            "early_finish",
            "late_start",
            "late_finish",
            "actual_start",
            "actual_finish",
            "duration_original",
            "duration_remaining",
            "percent_complete",
            "duration_percent_complete",
            "physical_percent_complete",
            "total_float",
            "derived_total_float_days",
            "explicit_total_float_days",
            "is_milestone",
            "wbs_code",
            "wbs_path",
            *extra,
        ),
        "schedule_file_imports": (
            "project_key",
            "schedule_version_key",
            "import_status",
            "created_at",
            "cost_loaded_status",
        ),
    }


def _contracts() -> tuple[VisualizationMetricContract, ...]:
    return (
        VisualizationMetricContract(
            metric_key="monthly_activity_start_finish_distribution",
            display_name="Monthly Activity Start/Finish Distribution",
            category="distribution",
            pm_facing_purpose="Show when starts and finishes fall by month across actual, planned, baseline, early, and late date families.",
            formula_summary="Bucket activity start and finish dates by month for each selected date family.",
            formula_detail=(
                "For each schedule version, count activity starts and finishes by calendar month. "
                "Use actual_start/actual_finish for actuals, planned_start/planned_finish or "
                "start_date/finish_date for planned/current dates, schedule_baseline_activities for "
                "baseline dates, and selected CPM result dates for computed early/late dates when available."
            ),
            source_tables=(
                "procore_ep_schedule_activities",
                "schedule_baseline_activities",
                "project_schedule_baseline_selections",
                "schedule_cpm_activity_results",
                "schedule_file_imports",
            ),
            source_columns={
                **_current_activity_columns(),
                "schedule_baseline_activities": (
                    "current_schedule_version_key",
                    "baseline_project_key",
                    "activity_id",
                    "planned_start",
                    "planned_finish",
                    "start_date",
                    "finish_date",
                    "early_start",
                    "early_finish",
                    "late_start",
                    "late_finish",
                ),
                "project_schedule_baseline_selections": (
                    "project_key",
                    "current_schedule_version_key",
                    "selected_baseline_schedule_version_key",
                    "selection_status",
                ),
                "schedule_cpm_activity_results": (
                    "schedule_version_key",
                    "cpm_run_id",
                    "activity_id",
                    "computed_early_start",
                    "computed_early_finish",
                    "computed_late_start",
                    "computed_late_finish",
                ),
            },
            udf_dependencies=(),
            comparison_basis=("current_update", "selected_baseline", "computed_cpm"),
            weighting_basis=("activity_count",),
            default_weighting_basis="activity_count",
            configurable_thresholds={"monthly_bucket_timezone": "project_local"},
            configurable_weights={},
            readiness_status="ready_after_trend_aggregation",
            blockers=("monthly aggregation API not implemented in Phase 5",),
            caveats=("Baseline buckets require selected baseline context when multiple baselines exist.",),
            future_api_payload_shape=_shape("project_key", "schedule_version_key", "month", "date_family", "start_count", "finish_count"),
            required_tests=("schema columns exist for mapped date families", "baseline and CPM date families are separately labeled"),
            notes=("Contract only; no chart aggregation is implemented in Phase 5.",),
            basis_labels=("source_export", "baseline", "selected_baseline", "computed_cpm", "current_update"),
        ),
        VisualizationMetricContract(
            metric_key="planned_vs_actual_percent_complete",
            display_name="Planned vs Actual Percent Complete",
            category="progress",
            pm_facing_purpose="Compare progress achieved by the data date with progress planned by the same date.",
            formula_summary="Default actual progress is duration weighted: sum(percent_complete * original_duration) / sum(original_duration).",
            formula_detail=(
                "Use duration_percent_complete when present, then percent_complete, then physical_percent_complete, with status-derived completion "
                "only as a clearly labeled fallback. Planned progress is the duration-weighted share planned complete by the data date. "
                "Activity-count weighting is a secondary variant. Cost weighting remains blocked until cost/resource loading is validated."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_file_imports"),
            source_columns=_current_activity_columns(),
            udf_dependencies=(),
            comparison_basis=("current_update", "prior_update"),
            weighting_basis=("duration_weighted", "activity_count", "cost_weighted_deferred"),
            default_weighting_basis="duration_weighted",
            configurable_thresholds={"minimum_duration_days": 0.0},
            configurable_weights={},
            readiness_status="ready_after_trend_aggregation",
            blockers=("trend aggregation by data date is not implemented", "cost-weighted variant requires cost/resource loading validation"),
            caveats=("Do not present cost-weighted progress as primary until cost/resource loading is verified.",),
            future_api_payload_shape=_shape("data_date", "planned_percent_complete", "actual_percent_complete", "weighting_basis"),
            required_tests=("duration-weighted default is declared", "cost-weighted variant is blocked"),
            notes=("This is a schedule-progress metric, not an earned-value certification.",),
            basis_labels=("source_export", "prior_update", "current_update"),
        ),
        VisualizationMetricContract(
            metric_key="schedule_performance_ratio",
            display_name="Schedule Performance Ratio",
            category="progress",
            pm_facing_purpose="Show schedule progress efficiency across updates without claiming earned-value SPI unless earned value basis is proven.",
            formula_summary="Default ratio is duration-weighted EV-like progress divided by duration-weighted PV-like planned progress.",
            formula_detail=(
                "EV-like progress = percent_complete * original_duration. PV-like planned progress = planned percent complete at data date * "
                "original_duration. Cost-weighted SPI is deferred until reliable cost/resource loading is proven."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_file_imports"),
            source_columns=_current_activity_columns(),
            udf_dependencies=(),
            comparison_basis=("current_update", "prior_update"),
            weighting_basis=("duration_weighted", "activity_count", "cost_weighted_deferred"),
            default_weighting_basis="duration_weighted",
            configurable_thresholds={"low_ratio_warning": 0.9, "low_ratio_fail": 0.8},
            configurable_weights={},
            readiness_status="ready_after_trend_aggregation",
            blockers=("trend aggregation by data date is not implemented", "earned-value/cost-weighted basis is not validated"),
            caveats=("Permitted display alias SPI must state this is duration-weighted schedule performance, not certified earned-value SPI.",),
            future_api_payload_shape=_shape("data_date", "schedule_performance_ratio", "ev_duration", "pv_duration", "weighting_basis"),
            required_tests=("duration-weighted default is declared", "cost-weighted SPI is blocked"),
            notes=("Display alias may include SPI only with explicit basis text.",),
            basis_labels=("source_export", "prior_update", "current_update"),
            display_aliases=("SPI-like duration ratio",),
        ),
        VisualizationMetricContract(
            metric_key="schedule_delay_over_time",
            display_name="Schedule Delay Over Time",
            category="trend",
            pm_facing_purpose="Show finish movement, gain, delay, baseline variance, and net movement across updates.",
            formula_summary="For each period, compare current forecast finish to prior forecast finish and selected baseline finish separately.",
            formula_detail=(
                "Period delay/gain uses prior-update context. Baseline variance uses selected baseline finish and must be labeled separately. "
                "Net movement is current forecast finish minus prior forecast finish."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_version_diffs", "project_schedule_baseline_selections", "schedule_baseline_projects"),
            source_columns={
                **_current_activity_columns(),
                "schedule_version_diffs": ("from_schedule_version_key", "to_schedule_version_key", "finish_drift_days", "created_at"),
                "project_schedule_baseline_selections": ("current_schedule_version_key", "selected_baseline_schedule_version_key", "selection_status"),
                "schedule_baseline_projects": ("baseline_project_key", "current_schedule_version_key", "scheduled_finish", "baseline_data_date"),
            },
            udf_dependencies=(),
            comparison_basis=("prior_update", "selected_baseline"),
            weighting_basis=("calendar_days",),
            default_weighting_basis="calendar_days",
            configurable_thresholds={"delay_warning_days": 7, "delay_fail_days": 14},
            configurable_weights={},
            readiness_status="ready_after_trend_aggregation",
            blockers=("multi-update trend API is not implemented"),
            caveats=(NON_CAUSATION_CAVEAT, "Update-to-update movement is not baseline variance."),
            future_api_payload_shape=_shape("period", "prior_version_key", "current_version_key", "prior_forecast_finish", "current_forecast_finish", "baseline_finish", "delay_days", "gain_days"),
            required_tests=("prior-update and baseline basis are both declared", "non-causation caveat is present"),
            notes=("Uses resolved forecast finish semantics from the canonical schedule hub services.",),
            basis_labels=("source_export", "prior_update", "selected_baseline", "baseline", "diff_derived"),
        ),
        VisualizationMetricContract(
            metric_key="schedule_changes_over_time",
            display_name="Schedule Changes Over Time",
            category="trend",
            pm_facing_purpose="Show how activity, logic, duration, criticality, lag, calendar, added, and deleted changes vary by update.",
            formula_summary="Aggregate persisted diff facts by update period and change category.",
            formula_detail=(
                "Use schedule_version_diffs for high-level counts, schedule_version_diff_detail_facts for activity/relationship/field changes, "
                "impact rollups for grouped impact counts, and selected CPM flags for critical and near-critical context."
            ),
            source_tables=("schedule_version_diffs", "schedule_version_diff_detail_facts", "schedule_version_diff_impact_rollups", "schedule_cpm_activity_results"),
            source_columns={
                "schedule_version_diffs": ("activity_added_count", "activity_removed_count", "activity_changed_count", "relationship_added_count", "relationship_removed_count", "calendar_churn_count", "code_churn_count"),
                "schedule_version_diff_detail_facts": ("diff_id", "change_domain", "change_type", "field_name", "day_delta", "is_critical_path_related"),
                "schedule_version_diff_impact_rollups": ("diff_id", "rollup_type", "change_count", "logic_change_count", "relationship_change_count", "activity_added_count", "activity_removed_count"),
                "schedule_cpm_activity_results": ("cpm_run_id", "activity_id", "computed_critical_flag", "computed_near_critical_flag"),
            },
            udf_dependencies=(),
            comparison_basis=("prior_update",),
            weighting_basis=("change_count",),
            default_weighting_basis="change_count",
            configurable_thresholds={"high_change_count": 100},
            configurable_weights={},
            readiness_status="ready_after_trend_aggregation",
            blockers=("multi-period diff aggregation API is not implemented"),
            caveats=("Critical and near-critical changes must use the selected CPM run, not all CPM rows.",),
            future_api_payload_shape=_shape("period", "change_category", "change_count", "critical_change_count"),
            required_tests=("diff source tables are mapped", "computed CPM criticality is labeled separately"),
            notes=("Relationship and duration details remain driver-drilldown facts unless promoted in a later API phase.",),
            basis_labels=("diff_derived", "computed_cpm", "prior_update"),
        ),
        VisualizationMetricContract(
            metric_key="delay_analysis",
            display_name="Delay Analysis",
            category="review_cue",
            pm_facing_purpose="Summarize period delays, gains, planned movement, likely review sequences, and affected WBS/phase.",
            formula_summary="Combine prior-update movement, diff impact rollups, and candidate driver facts for PM review.",
            formula_detail=(
                "For each period, compute delay/gain/net movement from resolved finish dates and attach candidate driver/WBS cues from diff detail "
                "and impact rollup facts. UDF-derived phase/area/subcontractor labels require normalization."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_version_diff_detail_facts", "schedule_version_diff_impact_rollups", "procore_ep_schedule_udf_values"),
            source_columns={
                **_current_activity_columns(),
                "schedule_version_diff_detail_facts": ("diff_id", "activity_id", "wbs_code", "change_domain", "change_type", "day_delta", "requires_attention"),
                "schedule_version_diff_impact_rollups": ("diff_id", "rollup_type", "wbs_code", "max_later_day_delta", "net_day_delta", "impact_score", "requires_attention"),
                "procore_ep_schedule_udf_values": ("schedule_version_key", "activity_id", "udf_type_name", "udf_value"),
            },
            udf_dependencies=("PHASE", "FLOOR", "SECTOR / AREA", "SUBCONTRACTOR", "Update Notes", "Schedule Review Comments"),
            comparison_basis=("prior_update",),
            weighting_basis=("day_delta", "impact_score"),
            default_weighting_basis="day_delta",
            configurable_thresholds={"candidate_driver_min_day_delta": 1},
            configurable_weights={},
            readiness_status="ready_after_udf_normalization",
            blockers=("prior-update diff evidence required for full delay review cues",),
            caveats=(NON_CAUSATION_CAVEAT,),
            future_api_payload_shape=_shape("period", "data_date", "schedule_end_date", "delays", "gains", "planned_movement", "net_movement", "candidate_driver", "primary_wbs_phase"),
            required_tests=("non-causation caveat is present", "UDF dependency blocks ready_now"),
            notes=("Candidate driver wording must stay advisory.",),
            basis_labels=("source_export", "diff_derived", "prior_update", "udf_derived"),
        ),
        VisualizationMetricContract(
            metric_key="window_start_accuracy",
            display_name="Window Start Accuracy",
            category="execution_reliability",
            pm_facing_purpose="Measure whether activities planned to start in a near-term update window actually started on time.",
            formula_summary="On-time starts divided by total planned starts in the configured window.",
            formula_detail=(
                "Default window is prior data date minus 7 days through current data date plus configured lookahead days. "
                "Classify each planned start as on time, late, or did not start using actual_start and selected planned-start basis."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_baseline_activities", "project_schedule_baseline_selections", "procore_ep_schedule_udf_values"),
            source_columns={
                **_current_activity_columns(),
                "schedule_baseline_activities": ("baseline_project_key", "activity_id", "planned_start", "start_date", "early_start"),
                "project_schedule_baseline_selections": ("project_key", "current_schedule_version_key", "selected_baseline_schedule_version_key"),
                "procore_ep_schedule_udf_values": ("schedule_version_key", "activity_id", "udf_type_name", "udf_value"),
            },
            udf_dependencies=("Filter Out", "Start Previous Status"),
            comparison_basis=("prior_update", "selected_baseline", "current_update"),
            weighting_basis=("activity_count",),
            default_weighting_basis="activity_count",
            configurable_thresholds={"lookback_days": 7, "lookahead_days": 21, "on_time_grace_days": 0},
            configurable_weights={},
            readiness_status="ready_after_udf_normalization",
            blockers=("UDF dimension coverage may be partial when named fields are sparse",),
            caveats=("The selected planned-start basis must be shown with the result.",),
            future_api_payload_shape=_shape("window_start", "window_end", "planned_start_basis", "on_time_count", "late_count", "did_not_start_count", "accuracy_ratio"),
            required_tests=("window thresholds are configurable", "UDF dependency blocks ready_now"),
            notes=("Can use prior update or selected baseline as planned-start basis in later APIs.",),
            basis_labels=("source_export", "selected_baseline", "baseline", "prior_update", "current_update", "udf_derived"),
        ),
        VisualizationMetricContract(
            metric_key="window_finish_accuracy",
            display_name="Window Finish Accuracy",
            category="execution_reliability",
            pm_facing_purpose="Measure whether activities planned to finish in a near-term update window actually finished on time.",
            formula_summary="Finished-on-time count divided by total planned finishes in the configured window.",
            formula_detail=(
                "Classify planned finishes as finished on time, finished late, or did not finish using actual_finish and the selected planned-finish basis. "
                "Default lookback/lookahead configuration mirrors start accuracy."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_baseline_activities", "project_schedule_baseline_selections", "procore_ep_schedule_udf_values"),
            source_columns={
                **_current_activity_columns(),
                "schedule_baseline_activities": ("baseline_project_key", "activity_id", "planned_finish", "finish_date", "early_finish"),
                "project_schedule_baseline_selections": ("project_key", "current_schedule_version_key", "selected_baseline_schedule_version_key"),
                "procore_ep_schedule_udf_values": ("schedule_version_key", "activity_id", "udf_type_name", "udf_value"),
            },
            udf_dependencies=("Filter Out", "Finish Previous Status"),
            comparison_basis=("prior_update", "selected_baseline", "current_update"),
            weighting_basis=("activity_count",),
            default_weighting_basis="activity_count",
            configurable_thresholds={"lookback_days": 7, "lookahead_days": 21, "on_time_grace_days": 0},
            configurable_weights={},
            readiness_status="ready_after_udf_normalization",
            blockers=("UDF dimension coverage may be partial when named fields are sparse",),
            caveats=("The selected planned-finish basis must be shown with the result.",),
            future_api_payload_shape=_shape("window_start", "window_end", "planned_finish_basis", "finished_on_time_count", "finished_late_count", "did_not_finish_count", "accuracy_ratio"),
            required_tests=("window thresholds are configurable", "UDF dependency blocks ready_now"),
            notes=("Supports future drilldown by due/not-finished classification.",),
            basis_labels=("source_export", "selected_baseline", "baseline", "prior_update", "current_update", "udf_derived"),
        ),
        VisualizationMetricContract(
            metric_key="should_have_finished_status",
            display_name="Should Have Finished Status",
            category="execution_reliability",
            pm_facing_purpose="Identify activities due to finish by the current data date and classify them for PM review.",
            formula_summary="Activities due by data date are classified as on track, at risk, or delayed using finish, progress, status, float, and criticality facts.",
            formula_detail=(
                "Use planned_finish or early_finish as the due basis, actual_finish for completion, current data date for due status, percent/status for progress, "
                "source/export total float, and selected computed CPM criticality where available."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_cpm_activity_results", "procore_ep_schedule_udf_values"),
            source_columns={
                **_current_activity_columns(),
                "schedule_cpm_activity_results": ("cpm_run_id", "activity_id", "computed_critical_flag", "computed_near_critical_flag", "computed_total_float"),
                "procore_ep_schedule_udf_values": ("schedule_version_key", "activity_id", "udf_type_name", "udf_value"),
            },
            udf_dependencies=("Filter Out", "Update Notes", "Schedule Review Comments"),
            comparison_basis=("current_update",),
            weighting_basis=("activity_count",),
            default_weighting_basis="activity_count",
            configurable_thresholds={"at_risk_float_days": 5, "critical_float_threshold_days": 1},
            configurable_weights={},
            readiness_status="ready_after_udf_normalization",
            blockers=("UDF comment/filter dimensions may be partial when named fields are sparse",),
            caveats=("Criticality must identify source/export float versus selected computed CPM criticality.",),
            future_api_payload_shape=_shape("status", "activity_count", "basis", "drilldown_url"),
            required_tests=("critical threshold is configurable", "UDF dependency blocks ready_now"),
            notes=("Output supports a future donut chart and activity drilldown.",),
            basis_labels=("source_export", "computed_cpm", "current_update", "udf_derived"),
        ),
        VisualizationMetricContract(
            metric_key="schedule_compression_ratio",
            display_name="Schedule Compression Ratio",
            category="feasibility",
            pm_facing_purpose="Measure execution intensity of remaining work versus a selected baseline or comparison update.",
            formula_summary="Compression percentage = ((baseline/comparison remaining duration / current remaining duration) - 1) * 100.",
            formula_detail=(
                "Compare matched unfinished activities between current and selected baseline/comparison version. Use duration_remaining or duration_original with explicit "
                "basis labels. TWNU07 may be a Tropical fixture baseline only and is not a product default."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_baseline_activities", "schedule_baseline_activity_crosswalk", "project_schedule_baseline_selections"),
            source_columns={
                **_current_activity_columns(),
                "schedule_baseline_activities": ("baseline_project_key", "activity_id", "duration_original", "duration_remaining", "actual_finish"),
                "schedule_baseline_activity_crosswalk": ("current_schedule_version_key", "baseline_project_key", "current_activity_id", "baseline_activity_id", "match_confidence", "review_required"),
                "project_schedule_baseline_selections": ("project_key", "current_schedule_version_key", "selected_baseline_schedule_version_key", "selection_status"),
            },
            udf_dependencies=(),
            comparison_basis=("selected_baseline", "prior_update"),
            weighting_basis=("duration_weighted",),
            default_weighting_basis="duration_weighted",
            configurable_thresholds={"green_max_percent": 14, "yellow_max_percent": 25, "red_min_percent": 26},
            configurable_weights={},
            readiness_status="ready_after_baseline_selection",
            blockers=("selected baseline/crosswalk must be confirmed for product use"),
            caveats=("Do not hard-code any Tropical fixture baseline as the global baseline.",),
            future_api_payload_shape=_shape("comparison_basis", "matched_remaining_count", "current_remaining_duration", "comparison_remaining_duration", "compression_percent", "status"),
            required_tests=("thresholds are configurable", "TWNU07 is not hard-coded"),
            notes=("Prior-update variant is allowed only when selected baseline is unavailable and labeled.",),
            basis_labels=("source_export", "baseline", "selected_baseline", "prior_update"),
        ),
        VisualizationMetricContract(
            metric_key="project_schedule_health_index",
            display_name="Project Schedule Health Index",
            category="quality",
            pm_facing_purpose="Provide a composite schedule reliability and usability score for PM review.",
            formula_summary="Weighted penalty model on a 0-100 scale using schedule quality, float, critical duration, constraints, update quality, and compression inputs.",
            formula_detail=(
                "Start from 100 and subtract configurable weighted penalties for logic density/open ends, negative/excessive float, high-duration critical/near-critical "
                "activities, constraint reliance, update quality, and compression overlay. Use existing quality scorecards where available."
            ),
            source_tables=("schedule_quality_evaluation_runs", "schedule_quality_metric_results", "schedule_quality_scorecards", "schedule_quality_findings", "procore_ep_schedule_activities", "schedule_cpm_activity_results"),
            source_columns={
                "schedule_quality_evaluation_runs": ("evaluation_run_id", "schedule_version_key", "status", "is_latest"),
                "schedule_quality_metric_results": ("metric_code", "metric_family", "numerator", "denominator", "value", "status"),
                "schedule_quality_scorecards": ("quality_score", "quality_grade", "finding_counts_json", "downstream_readiness_json"),
                "schedule_quality_findings": ("finding_code", "severity", "category", "activity_id"),
                **_current_activity_columns(),
                "schedule_cpm_activity_results": ("cpm_run_id", "activity_id", "computed_critical_flag", "computed_near_critical_flag", "computed_total_float"),
            },
            udf_dependencies=(),
            comparison_basis=("current_update", "selected_baseline"),
            weighting_basis=("weighted_penalty_model",),
            default_weighting_basis="weighted_penalty_model",
            configurable_thresholds={"green_min_score": 85, "yellow_min_score": 70},
            configurable_weights={"logic_density": 0.2, "float": 0.2, "critical_duration": 0.15, "constraints": 0.15, "update_quality": 0.2, "compression": 0.1},
            readiness_status="ready_after_trend_aggregation",
            blockers=("composite aggregation API is not implemented", "compression overlay depends on selected baseline readiness"),
            caveats=("Composite score should expose component penalties, not only the final number.",),
            future_api_payload_shape=_shape("schedule_version_key", "health_index", "grade", "component_scores", "weights"),
            required_tests=("weights are configurable", "quality tables are mapped"),
            notes=("Existing quality tables are first-class inputs; Phase 5 does not compute the score.",),
            basis_labels=("quality_derived", "source_export", "computed_cpm", "selected_baseline", "current_update"),
        ),
        VisualizationMetricContract(
            metric_key="schedule_feasibility_score",
            display_name="Schedule Feasibility Score",
            category="feasibility",
            pm_facing_purpose="Summarize forward-looking realism of the remaining schedule.",
            formula_summary="Composite score from compression, negative float, health index, schedule performance ratio, and forecast completion variance.",
            formula_detail=(
                "Combine normalized inputs from schedule_compression_ratio, source/export negative float, project_schedule_health_index, "
                "schedule_performance_ratio, and forecast finish variance. Each dependency must expose its own basis."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_quality_scorecards", "schedule_cpm_activity_results", "project_schedule_baseline_selections"),
            source_columns={
                **_current_activity_columns(),
                "schedule_quality_scorecards": ("quality_score", "quality_grade", "downstream_readiness_json"),
                "schedule_cpm_activity_results": ("computed_critical_flag", "computed_near_critical_flag", "computed_total_float"),
                "project_schedule_baseline_selections": ("current_schedule_version_key", "selected_baseline_schedule_version_key"),
            },
            udf_dependencies=(),
            comparison_basis=("current_update", "selected_baseline", "prior_update"),
            weighting_basis=("weighted_composite",),
            default_weighting_basis="weighted_composite",
            configurable_thresholds={"green_min_score": 80, "yellow_min_score": 65},
            configurable_weights={"compression": 0.25, "negative_float": 0.2, "health_index": 0.25, "performance_ratio": 0.15, "forecast_variance": 0.15},
            readiness_status="ready_after_trend_aggregation",
            blockers=("depends on schedule compression, health index, and performance ratio APIs"),
            caveats=("Composite feasibility is advisory and should show dependency readiness.",),
            future_api_payload_shape=_shape("schedule_version_key", "feasibility_score", "component_scores", "dependency_readiness"),
            required_tests=("dependency map includes upstream metrics", "weights are configurable"),
            notes=("Not ready until dependent metric APIs exist.",),
            basis_labels=("source_export", "computed_cpm", "quality_derived", "selected_baseline", "prior_update", "current_update"),
        ),
        VisualizationMetricContract(
            metric_key="required_recovery_days",
            display_name="Required Recovery Days",
            category="feasibility",
            pm_facing_purpose="Quantify implied future recovery built into the current forecast.",
            formula_summary="Required recovery days = critical path delay minus forecast finish movement.",
            formula_detail=(
                "Critical path delay should come from selected computed CPM path/criticality facts when available. Forecast finish movement uses prior-update "
                "resolved finish semantics. If CPM path delay is unavailable, classify as blocked rather than substituting source float."
            ),
            source_tables=("schedule_cpm_paths", "schedule_cpm_path_activities", "schedule_cpm_activity_results", "procore_ep_schedule_activities"),
            source_columns={
                "schedule_cpm_paths": ("cpm_run_id", "path_type", "path_duration", "path_finish_offset_days", "path_total_float", "path_status"),
                "schedule_cpm_path_activities": ("path_id", "activity_id", "computed_early_finish", "computed_late_finish", "computed_total_float", "path_sequence"),
                "schedule_cpm_activity_results": ("cpm_run_id", "activity_id", "computed_critical_flag", "computed_total_float"),
                **_current_activity_columns(),
            },
            udf_dependencies=(),
            comparison_basis=("prior_update", "computed_cpm"),
            weighting_basis=("calendar_days",),
            default_weighting_basis="calendar_days",
            configurable_thresholds={"recovery_warning_days": 5, "recovery_fail_days": 10},
            configurable_weights={},
            readiness_status="ready_after_trend_aggregation",
            blockers=("critical-path delay trend API is not implemented"),
            caveats=(NON_CAUSATION_CAVEAT, "Do not conflate critical path list length with critical remaining count."),
            future_api_payload_shape=_shape("period", "critical_path_delay_days", "forecast_finish_movement_days", "required_recovery_days"),
            required_tests=("non-causation caveat is present", "computed CPM basis is declared"),
            notes=("Uses selected CPM run/path provenance from Phase 3.",),
            basis_labels=("computed_cpm", "prior_update", "source_export"),
        ),
        VisualizationMetricContract(
            metric_key="critical_path_length_index",
            display_name="Critical Path Length Index",
            category="critical_path",
            pm_facing_purpose="Measure critical-path execution performance using an explicitly labeled criticality basis.",
            formula_summary="Compare critical/near-critical progress against planned progress using duration-weighted path or subset durations.",
            formula_detail=(
                "Prefer selected application-computed CPM criticality and path membership. Source/export total float can be a separately labeled fallback. "
                "Critical threshold defaults to total float <= 1 working day and must be configurable."
            ),
            source_tables=("schedule_cpm_paths", "schedule_cpm_path_activities", "schedule_cpm_activity_results", "procore_ep_schedule_activities"),
            source_columns={
                "schedule_cpm_paths": ("cpm_run_id", "path_duration", "path_total_float", "path_status"),
                "schedule_cpm_path_activities": ("path_id", "activity_id", "duration_value", "computed_total_float", "path_sequence"),
                "schedule_cpm_activity_results": ("computed_critical_flag", "computed_near_critical_flag", "critical_float_threshold_days", "near_critical_float_threshold_days"),
                **_current_activity_columns(),
            },
            udf_dependencies=(),
            comparison_basis=("computed_cpm", "current_update", "prior_update"),
            weighting_basis=("duration_weighted",),
            default_weighting_basis="duration_weighted",
            configurable_thresholds={"critical_float_threshold_days": 1, "near_critical_float_threshold_days": 10},
            configurable_weights={},
            readiness_status="ready_after_trend_aggregation",
            blockers=("critical path trend aggregation API is not implemented"),
            caveats=("Criticality source must be displayed as computed CPM or source/export float fallback.",),
            future_api_payload_shape=_shape("data_date", "criticality_basis", "critical_path_length_index", "thresholds"),
            required_tests=("critical threshold is configurable", "computed CPM basis is preferred"),
            notes=("Analog metric; not a proprietary product metric.",),
            basis_labels=("computed_cpm", "source_export", "prior_update", "current_update"),
        ),
        VisualizationMetricContract(
            metric_key="total_float_consumption_index",
            display_name="Total Float Consumption Index",
            category="critical_path",
            pm_facing_purpose="Measure erosion of float across critical and near-critical activities.",
            formula_summary="Float consumed between updates divided by elapsed time or planned float allowance for the selected critical/near-critical subset.",
            formula_detail=(
                "Use prior and current float values from the same labeled source. Computed CPM float and source/export float must not be mixed without labeling. "
                "Critical/near-critical subset should use selected computed CPM flags when available."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_cpm_activity_results"),
            source_columns={
                **_current_activity_columns(),
                "schedule_cpm_activity_results": ("cpm_run_id", "activity_id", "computed_total_float", "computed_critical_flag", "computed_near_critical_flag"),
            },
            udf_dependencies=(),
            comparison_basis=("prior_update", "computed_cpm"),
            weighting_basis=("float_days", "elapsed_days"),
            default_weighting_basis="float_days",
            configurable_thresholds={"high_consumption_ratio": 1.0},
            configurable_weights={},
            readiness_status="ready_after_trend_aggregation",
            blockers=("multi-update float aggregation API is not implemented"),
            caveats=("Source/export float and computed CPM float must remain separate.",),
            future_api_payload_shape=_shape("period", "float_basis", "criticality_basis", "float_consumed_days", "elapsed_days", "consumption_index"),
            required_tests=("float basis separation is declared", "computed CPM/source export labels are present"),
            notes=("This is an analog index and should not reuse proprietary names internally.",),
            basis_labels=("source_export", "computed_cpm", "prior_update", "current_update"),
        ),
        VisualizationMetricContract(
            metric_key="critical_issues_category_model",
            display_name="Critical Issues Category Model",
            category="review_cue",
            pm_facing_purpose="Define issue categories for critical issue panels and category-level review cues.",
            formula_summary="Classify issue candidates into five PM-facing categories with severity, drilldown basis, review eligibility, and caveats.",
            formula_detail=(
                "Categories: negative float and critical path erosion; schedule compression on critical path; logic and quality findings; execution and status gaps; "
                "review and external flags. Use review items/events only as workflow evidence, not causation findings."
            ),
            source_tables=("procore_ep_schedule_activities", "schedule_cpm_activity_results", "schedule_quality_findings", "schedule_quality_metric_results", "project_schedule_review_items", "project_schedule_review_item_events", "procore_ep_schedule_udf_values"),
            source_columns={
                **_current_activity_columns(),
                "schedule_cpm_activity_results": ("computed_critical_flag", "computed_near_critical_flag", "computed_total_float"),
                "schedule_quality_findings": ("finding_code", "severity", "category", "activity_id"),
                "schedule_quality_metric_results": ("metric_code", "metric_family", "value", "status"),
                "project_schedule_review_items": ("stable_item_key", "item_type", "priority", "review_status", "source_activity_id"),
                "project_schedule_review_item_events": ("event_type", "prior_status", "new_status", "operator_id"),
                "procore_ep_schedule_udf_values": ("schedule_version_key", "activity_id", "udf_type_name", "udf_value"),
            },
            udf_dependencies=("Update Notes", "Schedule Review Comments", "SUBCONTRACTOR", "Cost Code"),
            comparison_basis=("current_update", "prior_update", "computed_cpm"),
            weighting_basis=("severity_model",),
            default_weighting_basis="severity_model",
            configurable_thresholds={"high_priority_min_score": 80, "medium_priority_min_score": 50},
            configurable_weights={"float_erosion": 0.25, "compression": 0.2, "logic_quality": 0.2, "execution_status": 0.2, "review_external": 0.15},
            readiness_status="ready_after_udf_normalization",
            blockers=(),
            caveats=(NON_CAUSATION_CAVEAT, "Review item eligibility is advisory until operator action."),
            future_api_payload_shape=_shape("category", "severity", "candidate_count", "drilldown_basis", "review_item_eligible"),
            required_tests=("five categories are documented", "non-causation caveat is present", "UDF dependency blocks ready_now"),
            notes=("Category-level review cues materialize in Phase 8C when candidate counts are positive.",),
            basis_labels=("source_export", "computed_cpm", "quality_derived", "prior_update", "current_update", "udf_derived"),
        ),
    )


VISUALIZATION_METRIC_CONTRACTS: tuple[VisualizationMetricContract, ...] = _contracts()


def get_visualization_metric_contracts() -> list[dict[str, Any]]:
    """Return JSON-safe visualization metric contracts."""
    return [contract.to_dict() for contract in VISUALIZATION_METRIC_CONTRACTS]


def get_visualization_metric_readiness_matrix() -> list[dict[str, Any]]:
    """Return a compact readiness view for implementation planning."""
    return [
        {
            "metric_key": contract.metric_key,
            "display_name": contract.display_name,
            "readiness_status": contract.readiness_status,
            "blockers": list(contract.blockers),
            "basis_labels": list(contract.basis_labels),
            "dependencies": _dependency_keys(contract),
        }
        for contract in VISUALIZATION_METRIC_CONTRACTS
    ]


class ProjectScheduleVisualizationMetricContractService:
    """Read-only service for Phase 5 visualization metric contracts."""

    def __init__(self, *, db_path: str | None = None) -> None:
        self._db_path = db_path

    def list_contracts(self) -> list[dict[str, Any]]:
        return get_visualization_metric_contracts()

    def readiness_matrix(self) -> list[dict[str, Any]]:
        return get_visualization_metric_readiness_matrix()

    def contract_by_key(self, metric_key: str) -> dict[str, Any]:
        for contract in VISUALIZATION_METRIC_CONTRACTS:
            if contract.metric_key == metric_key:
                return contract.to_dict()
        raise KeyError(metric_key)

    def table_inventory(self) -> list[dict[str, Any]]:
        if not self._db_path:
            return []
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        return [{"table_name": str(row["name"])} for row in rows]

    def column_mapping_summary(self) -> dict[str, Any]:
        mapped = _merged_source_columns(VISUALIZATION_METRIC_CONTRACTS)
        if not self._db_path:
            return {"tables": mapped, "validation": {}}
        validation: dict[str, Any] = {}
        with open_connection(self._db_path) as conn:
            for table, columns in mapped.items():
                actual = _table_columns(conn, table)
                validation[table] = {
                    "mapped_columns": list(columns),
                    "actual_columns": actual,
                    "missing_columns": [column for column in columns if column not in actual],
                    "present": bool(actual),
                }
        return {"tables": mapped, "validation": validation}

    def udf_availability_summary(self) -> dict[str, Any]:
        from .project_schedule_udf_normalization_service import (
            UDF_FIELD_ALIASES,
            ProjectScheduleUdfNormalizationService,
        )

        contract_dependencies = sorted(
            {udf for contract in VISUALIZATION_METRIC_CONTRACTS for udf in contract.udf_dependencies}
        )
        base = {
            "required_named_udfs": list(REQUIRED_NAMED_UDFS),
            "contract_udf_dependencies": contract_dependencies,
            "generic_udf_table": "procore_ep_schedule_udf_values",
            "stable_named_udf_normalization_proven": True,
            "normalization_approach": "read_through_service",
            "internal_field_aliases": {field: list(aliases) for field, aliases in UDF_FIELD_ALIASES.items()},
            "readiness_rule": "Named UDF-dependent metrics cannot be ready_now until normalized queryable UDF semantics are proven.",
        }
        if not self._db_path:
            return base
        with open_connection(self._db_path) as conn:
            actual = _table_columns(conn, "procore_ep_schedule_udf_values")
        return {
            **base,
            "generic_udf_table_columns": actual,
            "generic_udf_table_present": bool(actual),
            "normalization_service": ProjectScheduleUdfNormalizationService(db_path=self._db_path).__class__.__name__,
        }

    def dependency_map(self) -> list[dict[str, Any]]:
        return [
            {
                "metric_key": contract.metric_key,
                "readiness_status": contract.readiness_status,
                "depends_on_metric_keys": _dependency_keys(contract),
                "depends_on_tables": list(contract.source_tables),
                "basis_labels": list(contract.basis_labels),
                "blockers": list(contract.blockers),
            }
            for contract in VISUALIZATION_METRIC_CONTRACTS
        ]


def _dependency_keys(contract: VisualizationMetricContract) -> list[str]:
    text = " ".join((contract.formula_detail, " ".join(contract.notes), " ".join(contract.blockers)))
    return [key for key in REQUIRED_METRIC_KEYS if key != contract.metric_key and key in text]


def _merged_source_columns(contracts: Iterable[VisualizationMetricContract]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}
    for contract in contracts:
        for table, columns in contract.source_columns.items():
            out.setdefault(table, set()).update(columns)
    return {table: sorted(columns) for table, columns in sorted(out.items())}


def _table_columns(conn: Any, table: str) -> list[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return []
    return [str(row["name"] if isinstance(row, dict) else row[1]) for row in rows]
