# Review Queue Contract

Every row must be raw-safe and bounded.

## Required fields

```json
{
  "subject_type": "task_candidate|commitment_candidate|daily_brief_action|accepted_task|accepted_commitment|follow_up_watch",
  "subject_id": "string",
  "candidate_id": "string|null",
  "family": "string",
  "source_family": "string|null",
  "title_redacted": "string|null",
  "reason_redacted": "string|null",
  "recommended_next_action_redacted": "string|null",
  "confidence": "number|null",
  "priority": "number|null",
  "project_key": "string|null",
  "project_resolution_status": "resolved|project_review_required|not_project_related|unknown",
  "source_ref_count": "number",
  "source_ref_coverage_status": "ok|source_missing|not_applicable",
  "candidate_status": "string|null",
  "review_status": "string|null",
  "accepted_status": "string|null",
  "watch_status": "string|null",
  "lifecycle_state": "string",
  "duplicate_group_key": "string",
  "age_bucket": "today|1_3d|4_7d|8_14d|15d_plus|unknown",
  "due_bucket": "overdue|today|next_3d|next_7d|future|none|unknown",
  "review_reason": "string|null",
  "disposition_reason_code": "string|null",
  "hidden_from_daily_brief": "boolean",
  "actionable": "boolean"
}
```

## Default filtering

Default review view includes:

- `new`
- `needs_review`
- `project_review_required`
- `stale`
- returned `snoozed`

Default review view excludes:

- future `snoozed`
- `rejected`
- `suppressed`
- `merged`
- `closed`

But excluded rows must be retrievable with explicit filters.

