# Prompt 03 — Lifecycle Event Store or State Model

## Objective

Implement the lifecycle event/store layer chosen in Prompt 01.

## Preferred implementation

If migration is needed, add an append-only event table:

```sql
candidate_lifecycle_events(
  lifecycle_event_id TEXT PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  candidate_id TEXT,
  family TEXT,
  event_type TEXT NOT NULL,
  prior_state TEXT,
  new_state TEXT,
  reason_code TEXT,
  reason_redacted TEXT,
  effective_until_utc TEXT,
  target_subject_type TEXT,
  target_subject_id TEXT,
  duplicate_group_key TEXT,
  reviewer_ref TEXT,
  created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  <phase 10 guard columns>
)
```

Add indexes on:

- `(subject_type, subject_id, created_utc)`
- `(candidate_id)`
- `(new_state)`
- `(duplicate_group_key)`
- `(effective_until_utc)`

Do not store raw notes. Store reason codes and bounded redacted notes only.

## Store helpers

Implement store methods for:

- insert lifecycle event idempotently
- list lifecycle events for subject
- latest lifecycle state for subjects
- latest lifecycle states by group key
- lifecycle counts by state
- guard-column check support

## Compatibility

- Keep existing `candidate_review_events` behavior intact.
- For task/commitment accept/reject/snooze/suppress, either mirror lifecycle events from the new operations or make the unified read model consume both existing review columns and new lifecycle events.
- Do not create dual truth that makes task/commitment status inconsistent.

## Tests

- event IDs deterministic
- duplicate event replay is no-op
- latest state selected deterministically
- guard columns zero
- existing Phase 10A review tests still pass

