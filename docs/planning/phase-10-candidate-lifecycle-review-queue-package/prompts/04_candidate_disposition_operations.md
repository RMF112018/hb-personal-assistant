# Prompt 04 — Candidate Disposition Operations

## Objective

Implement deterministic local-only operations for candidate disposition.

## Operations

- accept
- reject with reason code
- snooze until date
- merge into candidate or accepted item
- close as complete/handled
- reopen
- mark duplicate
- suppress recurring false positive

## Rules

- Every operation requires an explicit `--db` for validation commands.
- Every operation is local DB only.
- All operations are idempotent.
- All operations emit raw-safe JSON.
- Single-item operations may apply immediately if consistent with existing CLI patterns.
- Batch/file operations must default to dry-run and require `--apply`.
- Existing `second-brain review` task/commitment behavior must not regress.
- Suppression must not delete candidates.
- Snooze must hide from normal daily brief until `effective_until_utc`, then return.
- Merge must preserve source refs from source and target through read-model visibility.

## Reason codes

Use `references/disposition_reason_codes.md`.

## Tests

Create `tests/test_phase_10_candidate_lifecycle_operations.py`.

Assertions:

- accept/reject/snooze/close/reopen/suppress are idempotent
- snoozed candidate hidden before return date and visible on/after return date
- rejected/suppressed hidden from normal queue/brief but visible in explicit views
- source-ref-missing candidate cannot be accepted/promoted without documented exception
- raw-free JSON output

