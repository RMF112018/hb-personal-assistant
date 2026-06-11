# Prompt 02 — Unified Review Queue Read Model

## Objective

Implement a deterministic raw-safe read model that unifies all eligible candidate/action families.

## Required sources

Include, unless repo truth documents an exclusion:

- `daily_brief_action_candidates`
- `task_candidates`
- `commitment_candidates`
- `follow_up_watch_items`
- `accepted_tasks`
- `accepted_commitments`
- `candidate_source_refs`
- project identity / alias tables where needed for status only

## Required row contract

Each row must include:

- `subject_type`
- `subject_id`
- `candidate_id` when applicable
- `family`
- `source_family`
- `title_redacted`
- `reason_redacted`
- `recommended_next_action_redacted`
- `confidence`
- `priority`
- `project_key`
- `project_resolution_status`
- `source_ref_count`
- `source_ref_coverage_status`
- `candidate_status`
- `review_status`
- `accepted_status`
- `watch_status`
- `lifecycle_state`
- `duplicate_group_key`
- `age_bucket`
- `due_bucket`
- `review_reason`
- `disposition_reason_code`
- `hidden_from_daily_brief`
- `actionable`

## State derivation

Use `references/lifecycle_state_contract.md`.

Rules:

- Existing task/commitment `review_status` remains canonical for those candidate rows.
- Daily-brief candidates derive state from `status`, source refs, project status, and lifecycle overlay.
- Accepted rows derive state from `status`, `completed_utc`, and lifecycle overlay.
- Follow-up watch rows derive state from `watch_status` and lifecycle overlay.
- Missing source refs must yield `source_missing` or withheld/degraded behavior.
- Missing project key for a project-like candidate must yield `project_review_required`, not hidden.

## Tests

Create `tests/test_phase_10_candidate_lifecycle_read_model.py`.

Minimum assertions:

- all eligible families are included
- only safe fields are emitted
- source-ref count/status computed correctly
- project-review-required remains visible
- rejected/suppressed/merged rows are visible in explicit all/status views but hidden from default normal view
- backward compatibility when lifecycle overlay tables are empty

## Evidence

Write `02_review_queue_sample.json` with bounded redacted sample rows or synthetic fixture output.

