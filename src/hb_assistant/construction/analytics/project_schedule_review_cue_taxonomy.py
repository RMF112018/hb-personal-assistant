"""PM-facing taxonomy labels for schedule review workbench cues."""

from __future__ import annotations

from typing import Any

_CUE_TAXONOMY: dict[str, dict[str, str]] = {
    "driver": {
        "cue_category": "change_driver",
        "cue_label": "Candidate change driver",
        "recommended_review_action": "Review the linked activity sequence and downstream movement before disposition.",
    },
    "milestone": {
        "cue_category": "milestone_movement",
        "cue_label": "Milestone moved later",
        "recommended_review_action": "Confirm milestone forecast movement against the current schedule update context.",
    },
    "negative_float": {
        "cue_category": "float_pressure",
        "cue_label": "Negative float remaining",
        "recommended_review_action": "Review remaining negative-float activities for recovery planning follow-up.",
    },
    "worsened_float": {
        "cue_category": "float_erosion",
        "cue_label": "Worsened float between updates",
        "recommended_review_action": "Compare float movement between updates and note recovery options for PM review.",
    },
    "critical_remaining": {
        "cue_category": "critical_path",
        "cue_label": "Critical remaining work",
        "recommended_review_action": "Review critical or near-critical remaining activities for sequencing follow-up.",
    },
    "metric_should_have_finished": {
        "cue_category": "execution_reliability",
        "cue_label": "Should have finished",
        "recommended_review_action": "Review overdue unfinished activities and confirm field status before disposition.",
    },
    "metric_window_start": {
        "cue_category": "start_reliability",
        "cue_label": "Window start miss",
        "recommended_review_action": "Review near-term start reliability against the current update window.",
    },
    "metric_window_finish": {
        "cue_category": "finish_reliability",
        "cue_label": "Window finish miss",
        "recommended_review_action": "Review near-term finish reliability against the current update window.",
    },
    "metric_critical_issues": {
        "cue_category": "issue_category",
        "cue_label": "Critical issue category",
        "recommended_review_action": "Review grouped critical-issue candidates and route follow-up by category.",
    },
    "metric_delay_analysis": {
        "cue_category": "period_movement",
        "cue_label": "Delay analysis cue",
        "recommended_review_action": "Review prior-update finish movement as a sequence cue, not a causation finding.",
    },
    "metric_quality_finding": {
        "cue_category": "schedule_quality",
        "cue_label": "Schedule quality finding",
        "recommended_review_action": "Review the schedule quality finding and confirm whether PM follow-up is needed.",
    },
    "metric_quality_open_start": {
        "cue_category": "schedule_quality",
        "cue_label": "Open starts detected",
        "recommended_review_action": "Review activities without predecessors and confirm whether open starts are intended.",
    },
    "metric_quality_open_finish": {
        "cue_category": "schedule_quality",
        "cue_label": "Open finishes detected",
        "recommended_review_action": "Review activities without successors and confirm whether open finishes are intended.",
    },
    "metric_quality_missing_logic": {
        "cue_category": "schedule_quality",
        "cue_label": "Logic integrity warning",
        "recommended_review_action": "Review logic integrity metrics and confirm whether relationship gaps need cleanup.",
    },
    "metric_quality_orphan_activity": {
        "cue_category": "schedule_quality",
        "cue_label": "Orphan relationship references",
        "recommended_review_action": "Review dangling relationship references in the schedule update.",
    },
    "metric_quality_duplicate_relationship": {
        "cue_category": "schedule_quality",
        "cue_label": "Duplicate relationships detected",
        "recommended_review_action": "Review duplicate relationship ties and confirm whether deduplication is needed.",
    },
    "metric_quality_self_relationship": {
        "cue_category": "schedule_quality",
        "cue_label": "Self relationships detected",
        "recommended_review_action": "Review self-referencing relationships for logic correctness.",
    },
    "metric_quality_lead": {
        "cue_category": "schedule_quality",
        "cue_label": "Leads (negative lag) detected",
        "recommended_review_action": "Review lead relationships and confirm whether negative lag is intended.",
    },
    "metric_quality_lag": {
        "cue_category": "schedule_quality",
        "cue_label": "Excessive lags detected",
        "recommended_review_action": "Review long lag values and confirm whether they reflect the plan.",
    },
    "metric_quality_hard_constraint": {
        "cue_category": "schedule_quality",
        "cue_label": "Hard constraints detected",
        "recommended_review_action": "Review hard-constrained activities and confirm constraint usage.",
    },
    "metric_quality_high_float": {
        "cue_category": "schedule_quality",
        "cue_label": "High float detected",
        "recommended_review_action": "Review high-float activities for potential logic gaps.",
    },
    "metric_quality_negative_float": {
        "cue_category": "schedule_quality",
        "cue_label": "Negative float quality signal",
        "recommended_review_action": "Review negative-float quality metrics alongside remaining float pressure.",
    },
    "metric_quality_high_duration": {
        "cue_category": "schedule_quality",
        "cue_label": "High duration activities detected",
        "recommended_review_action": "Review long-duration activities for decomposition or reasonableness.",
    },
    "metric_quality_invalid_date": {
        "cue_category": "schedule_quality",
        "cue_label": "Invalid dates detected",
        "recommended_review_action": "Review invalid or inconsistent dates before relying on forecast dates.",
    },
    "metric_quality_critical_path_readiness": {
        "cue_category": "schedule_quality",
        "cue_label": "Critical path readiness gap",
        "recommended_review_action": "Review critical-path readiness before relying on driving-path analytics.",
    },
    "metric_quality_cost_resource_readiness": {
        "cue_category": "schedule_quality",
        "cue_label": "Cost/resource readiness gap",
        "recommended_review_action": "Review cost and resource loading readiness for this schedule update.",
    },
    "metric_compression_readiness": {
        "cue_category": "compression_readiness",
        "cue_label": "Compression readiness blocker",
        "recommended_review_action": "Resolve selected-baseline compression readiness blockers before relying on the metric.",
    },
    "readiness_preview": {
        "cue_category": "metric_readiness",
        "cue_label": "Metric readiness preview",
        "recommended_review_action": "Metric is readiness-only; no persisted review item was materialized.",
    },
}

_DEFAULT_TAXONOMY = {
    "cue_category": "schedule_review",
    "cue_label": "Schedule review cue",
    "recommended_review_action": "Review the schedule-control cue and record PM disposition when appropriate.",
}


def taxonomy_for_item_type(item_type: str) -> dict[str, str]:
    return dict(_CUE_TAXONOMY.get(item_type, _DEFAULT_TAXONOMY))


def apply_taxonomy_fields(*, item_type: str, evidence: dict[str, Any]) -> dict[str, Any]:
    taxonomy = taxonomy_for_item_type(item_type)
    enriched = dict(evidence)
    enriched.setdefault("cue_category", taxonomy["cue_category"])
    enriched.setdefault("cue_label", taxonomy["cue_label"])
    enriched.setdefault("recommended_review_action", taxonomy["recommended_review_action"])
    return enriched
