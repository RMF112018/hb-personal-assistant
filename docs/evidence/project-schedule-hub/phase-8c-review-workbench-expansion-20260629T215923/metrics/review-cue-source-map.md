# Review Cue Source Map

```json
[
  {
    "source_metric_key": "change_driver_analysis",
    "signal_types": [
      "driver"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "milestones",
    "signal_types": [
      "milestone_moved_later"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "remaining_health",
    "signal_types": [
      "negative_float"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "schedule_changes_over_time",
    "signal_types": [
      "worsened_float"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "critical_path_length_index",
    "signal_types": [
      "critical_remaining"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "should_have_finished_status",
    "signal_types": [
      "at_risk_activity",
      "delayed_activity"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "window_start_accuracy",
    "signal_types": [
      "late_start",
      "did_not_start"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "window_finish_accuracy",
    "signal_types": [
      "late_finish",
      "did_not_finish"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "critical_issues_category_model",
    "signal_types": [
      "issue_category"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "delay_analysis",
    "signal_types": [
      "period_movement"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "schedule_quality_findings",
    "signal_types": [
      "quality_finding"
    ],
    "materializable": true
  },
  {
    "source_metric_key": "schedule_compression_ratio",
    "signal_types": [
      "compression_readiness"
    ],
    "materializable": true
  }
]
```
