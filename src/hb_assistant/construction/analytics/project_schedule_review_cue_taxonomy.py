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
