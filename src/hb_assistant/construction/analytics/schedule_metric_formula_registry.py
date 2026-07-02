"""Deterministic schedule metric formula registry for proof export."""

from __future__ import annotations

from typing import Any

FORMULA_VERSION = "2026-07-02.schedule-metric-formula-proof.v1"
ZERO_DENOMINATOR_POLICY = "not_computable"

# Frontend trend fetch list (ProjectSchedulePage SCHEDULE_CONTROLS_METRICS)
FRONTEND_CHART_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "monthly_activity_start_finish_distribution",
        "planned_vs_actual_percent_complete",
        "schedule_performance_ratio",
        "schedule_delay_over_time",
        "schedule_changes_over_time",
        "project_schedule_health_index",
        "schedule_feasibility_score",
        "required_recovery_days",
        "critical_path_length_index",
        "total_float_consumption_index",
        "delay_analysis",
        "window_start_accuracy",
        "window_finish_accuracy",
        "should_have_finished_status",
        "critical_issues_category_model",
        "schedule_compression_ratio",
    }
)

TREND_API_METRIC_KEYS: frozenset[str] = FRONTEND_CHART_METRIC_KEYS

PROOF_ONLY_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "schedule_compression_index_internal",
        "future_acceleration",
        "critical_indices",
    }
)

HEALTH_WEIGHTS: dict[str, float] = {
    "logic_density": 0.2,
    "float": 0.2,
    "critical_duration": 0.15,
    "constraints": 0.15,
    "update_quality": 0.2,
    "compression": 0.1,
}

FEASIBILITY_WEIGHTS: dict[str, float] = {
    "compression": 0.25,
    "negative_float": 0.2,
    "health_index": 0.25,
    "performance_ratio": 0.15,
    "forecast_variance": 0.15,
}


def _entry(
    *,
    metric_key: str,
    display_name: str,
    formula_family: str,
    formula_expression: str,
    inputs: list[str],
    outputs: list[str],
    weighting_basis: str = "not_applicable",
    formula_supported: bool = True,
    proof_supported: bool = True,
    api_active: bool = True,
    chart_active: bool | None = None,
    reason_chart_inactive: str | None = None,
    weighting_policy_validated: bool = False,
    supported: bool = True,
    reason: str | None = None,
    limitations: list[str] | None = None,
    pm_safe_description: str = "",
) -> dict[str, Any]:
    if chart_active is None:
        chart_active = metric_key in FRONTEND_CHART_METRIC_KEYS
    if not chart_active and reason_chart_inactive is None:
        reason_chart_inactive = (
            "Not wired into screenshot/dashboard chart."
            if metric_key in PROOF_ONLY_METRIC_KEYS
            else None
        )
    return {
        "metric_key": metric_key,
        "display_name": display_name,
        "formula_family": formula_family,
        "formula_version": FORMULA_VERSION,
        "formula_expression": formula_expression,
        "inputs": inputs,
        "outputs": outputs,
        "weighting_basis": weighting_basis,
        "formula_supported": formula_supported,
        "proof_supported": proof_supported,
        "api_active": api_active,
        "chart_active": chart_active,
        "reason_chart_inactive": reason_chart_inactive,
        "zero_denominator_policy": ZERO_DENOMINATOR_POLICY,
        "weighting_policy_validated": weighting_policy_validated,
        "supported": supported,
        "reason": reason,
        "limitations": limitations or [],
        "pm_safe_description": pm_safe_description,
    }


def build_metric_registry() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = [
        _entry(
            metric_key="planned_vs_actual_percent_complete_duration_weighted",
            display_name="Planned vs Actual Percent Complete (duration weighted)",
            formula_family="progress_curve",
            formula_expression="actual_complete_duration / total_duration; planned_complete_duration / total_duration",
            inputs=["procore_ep_schedule_activities.duration_original", "data_date", "actual_finish"],
            outputs=["actual_percent_complete", "planned_percent_complete", "variance"],
            weighting_basis="duration_weighted",
            pm_safe_description="Duration-weighted progress curve for PM schedule review.",
        ),
        _entry(
            metric_key="planned_vs_actual_percent_complete_activity_count",
            display_name="Planned vs Actual Percent Complete (activity count)",
            formula_family="progress_curve",
            formula_expression="actual_complete_activity_count / total_activity_count",
            inputs=["procore_ep_schedule_activities", "data_date"],
            outputs=["actual_percent_complete", "planned_percent_complete"],
            weighting_basis="activity_count",
            pm_safe_description="Activity-count progress curve.",
        ),
        _entry(
            metric_key="planned_vs_actual_percent_complete",
            display_name="Planned vs Actual Percent Complete",
            formula_family="progress_curve",
            formula_expression="See duration_weighted and activity_count variants",
            inputs=["procore_ep_schedule_activities"],
            outputs=["actual_percent_complete", "planned_percent_complete", "variance"],
            weighting_basis="duration_weighted|activity_count",
            pm_safe_description="Default dashboard metric; duration-weighted unless alternate basis selected.",
        ),
        _entry(
            metric_key="schedule_spi_count",
            display_name="Internal Schedule SPI (count)",
            formula_family="schedule_spi",
            formula_expression="actual_complete_activity_count / planned_complete_activity_count",
            inputs=["activity counts by data_date"],
            outputs=["schedule_spi", "numerator", "denominator"],
            weighting_basis="activity_count",
            pm_safe_description="Internal schedule SPI — not earned-value SPI.",
        ),
        _entry(
            metric_key="schedule_spi_duration",
            display_name="Internal Schedule SPI (duration)",
            formula_family="schedule_spi",
            formula_expression="actual_complete_duration / planned_complete_duration",
            inputs=["duration_original", "data_date"],
            outputs=["schedule_spi", "numerator", "denominator"],
            weighting_basis="duration_weighted",
            pm_safe_description="Internal duration-weighted schedule SPI — not earned-value SPI.",
        ),
        _entry(
            metric_key="schedule_performance_ratio",
            display_name="Schedule Performance Index",
            formula_family="schedule_spi",
            formula_expression="actual_complete / planned_complete (same as internal schedule SPI)",
            inputs=["progress curve operands"],
            outputs=["schedule_performance_ratio"],
            weighting_basis="duration_weighted",
            pm_safe_description="Dashboard alias for internal schedule SPI.",
        ),
        _entry(
            metric_key="schedule_changes_over_time",
            display_name="Schedule Changes Over Time",
            formula_family="diff_aggregation",
            formula_expression="Aggregate schedule_version_diffs + detail_facts categories per update period",
            inputs=["schedule_version_diffs", "schedule_version_diff_detail_facts"],
            outputs=["added_activity_count", "duration_change_count", "near_critical_change_count"],
            pm_safe_description="Observed schedule change counts between updates.",
        ),
        _entry(
            metric_key="schedule_delay_over_time",
            display_name="Schedule Delay Over Time",
            formula_family="delay_trend",
            formula_expression="delay_days = current_forecast_finish - comparison_finish (positive=delay)",
            inputs=["forecast_finish", "comparison_finish", "comparison_basis"],
            outputs=["delay_days", "gain_days", "net_movement_days"],
            pm_safe_description="Observed forecast finish movement between comparison bases.",
        ),
        _entry(
            metric_key="delay_analysis",
            display_name="Delay Analysis",
            formula_family="delay_analysis",
            formula_expression="period_finish_movement_days = current_finish - prior_finish",
            inputs=["finish dates", "prior_update diff"],
            outputs=["period_gain_or_delay classification"],
            pm_safe_description="Advisory delay movement summary; not causation or compensability claims.",
        ),
        _entry(
            metric_key="window_start_accuracy",
            display_name="Window Start Accuracy",
            formula_family="window_accuracy",
            formula_expression="window_start_accuracy_days = actual_start - planned_window_start",
            inputs=["activity start dates", "window basis"],
            outputs=["early", "on_time", "late counts"],
            pm_safe_description="Start accuracy within defined lookback/lookahead window.",
        ),
        _entry(
            metric_key="should_have_finished_status",
            display_name="Should Have Finished",
            formula_family="due_date_classification",
            formula_expression="should_have_finished = planned_finish <= data_date",
            inputs=["planned_finish", "actual_finish", "data_date"],
            outputs=["classification", "days_late_or_until_due"],
            pm_safe_description="Activities due by data date classified for PM review.",
        ),
        _entry(
            metric_key="critical_issues_category_model",
            display_name="Critical Issues / Critical Indices Panel",
            formula_family="critical_issues",
            formula_expression="Deterministic category counts from CPM, quality, review items",
            inputs=["schedule_cpm_activity_results", "schedule_quality_findings"],
            outputs=["negative_float_count", "critical_activity_count"],
            weighting_policy_validated=False,
            limitations=["Category thresholds are policy choices."],
            pm_safe_description="Critical issue burden categories for dashboard panel.",
        ),
        _entry(
            metric_key="schedule_compression_index_internal",
            display_name="Schedule Compression Index (internal analog)",
            formula_family="compression_analog",
            formula_expression="max(0, required_recovery_days) / remaining_duration_days",
            inputs=["forecast_finish", "target_finish", "data_date"],
            outputs=["index", "numerator", "denominator"],
            chart_active=False,
            reason_chart_inactive="Proof-only internal analog; not SmartPM equivalent.",
            weighting_policy_validated=False,
            limitations=["Internal analog only — not SmartPM equivalence."],
            pm_safe_description="Internal compression analog for proof; not a certified SmartPM metric.",
        ),
        _entry(
            metric_key="project_schedule_health_index",
            display_name="Project Schedule Health Index",
            formula_family="weighted_composite",
            formula_expression="100 - sum(weighted_penalties) with visible component scores",
            inputs=["quality metrics", "CPM float", "findings"],
            outputs=["score", "components"],
            weighting_basis="weighted_penalty_model",
            weighting_policy_validated=False,
            limitations=["Weights require PM/business validation."],
            pm_safe_description="Deterministic composite health score with exposed weights.",
        ),
        _entry(
            metric_key="schedule_feasibility_score",
            display_name="Schedule Feasibility Score",
            formula_family="weighted_composite",
            formula_expression="Weighted composite of compression, float, health, SPI, forecast variance",
            inputs=["dependency metrics"],
            outputs=["score", "components", "dependency_readiness"],
            weighting_basis="weighted_composite",
            weighting_policy_validated=False,
            limitations=["Weights and dependency gates require PM/business validation."],
            pm_safe_description="Forward-looking feasibility composite with exposed weights.",
        ),
        _entry(
            metric_key="future_acceleration",
            display_name="Future Acceleration",
            formula_family="acceleration",
            formula_expression="future_acceleration_ratio = required_recovery_days / remaining_days",
            inputs=["forecast_finish", "target_finish", "data_date"],
            outputs=["ratio", "classification"],
            chart_active=False,
            reason_chart_inactive="Proof-only; not yet on dashboard chart.",
            pm_safe_description="Observed acceleration ratio needed to recover target finish.",
        ),
        _entry(
            metric_key="critical_indices",
            display_name="Critical Indices",
            formula_family="critical_ratios",
            formula_expression="critical_activity_ratio = critical_count / total_activity_count",
            inputs=["schedule_cpm_activity_results", "activity count"],
            outputs=["critical_activity_ratio", "near_critical_activity_ratio"],
            chart_active=False,
            reason_chart_inactive="Proof bundle; partial coverage exists via critical_path_length_index chart.",
            weighting_policy_validated=False,
            pm_safe_description="Criticality burden ratios with explicit denominators.",
        ),
        _entry(
            metric_key="earned_value_spi",
            display_name="Earned Value SPI",
            formula_family="schedule_spi",
            formula_expression="earned_value / planned_value",
            inputs=["planned_value", "earned_value"],
            outputs=["earned_value_spi"],
            formula_supported=False,
            proof_supported=False,
            api_active=False,
            chart_active=False,
            supported=False,
            reason="requires validated planned value and earned value basis",
            pm_safe_description="Not supported without EV basis.",
        ),
        _entry(
            metric_key="cost_weighted_percent_complete",
            display_name="Cost-Weighted Percent Complete",
            formula_family="progress_curve",
            formula_expression="cost-weighted progress",
            inputs=["cost-loaded schedule"],
            outputs=["percent_complete"],
            weighting_basis="cost_weighted",
            formula_supported=False,
            proof_supported=False,
            supported=False,
            reason="requires validated cost-loaded schedule data",
        ),
        _entry(
            metric_key="resource_weighted_percent_complete",
            display_name="Resource-Weighted Percent Complete",
            formula_family="progress_curve",
            formula_expression="resource-weighted progress",
            inputs=["resource-loaded schedule"],
            outputs=["percent_complete"],
            weighting_basis="resource_weighted",
            formula_supported=False,
            proof_supported=False,
            supported=False,
            reason="requires validated resource-loaded schedule data",
        ),
    ]
    return entries


def registry_by_key() -> dict[str, dict[str, Any]]:
    return {e["metric_key"]: e for e in build_metric_registry()}


def all_prompt_metric_keys() -> list[str]:
    return [
        "planned_vs_actual_percent_complete",
        "schedule_spi_count",
        "schedule_spi_duration",
        "schedule_performance_ratio",
        "schedule_changes_over_time",
        "schedule_delay_over_time",
        "delay_analysis",
        "window_start_accuracy",
        "should_have_finished_status",
        "critical_issues_category_model",
        "schedule_compression_index_internal",
        "project_schedule_health_index",
        "schedule_feasibility_score",
        "future_acceleration",
        "critical_indices",
        "earned_value_spi",
        "cost_weighted_percent_complete",
        "resource_weighted_percent_complete",
    ]


__all__ = [
    "FORMULA_VERSION",
    "FRONTEND_CHART_METRIC_KEYS",
    "PROOF_ONLY_METRIC_KEYS",
    "TREND_API_METRIC_KEYS",
    "ZERO_DENOMINATOR_POLICY",
    "all_prompt_metric_keys",
    "build_metric_registry",
    "registry_by_key",
]
