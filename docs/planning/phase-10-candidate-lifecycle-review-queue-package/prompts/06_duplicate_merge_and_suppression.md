# Prompt 06 — Duplicate, Merge, and Suppression

## Objective

Prevent duplicate review noise and support auditable merge/suppression behavior.

## Duplicate group key

Compute deterministic duplicate group keys using ordered fallbacks:

1. source family + source ref hash
2. thread ref / message hash when available
3. stable key when available
4. family + project key + normalized redacted title hash + due bucket
5. subject type + subject id as last-resort singleton

Never include raw text. Normalize already-redacted title/reason only.

## Merge links

If schema is required, add:

```sql
candidate_merge_links(
  merge_link_id TEXT PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  source_subject_type TEXT NOT NULL,
  source_subject_id TEXT NOT NULL,
  target_subject_type TEXT NOT NULL,
  target_subject_id TEXT NOT NULL,
  duplicate_group_key TEXT,
  merge_reason_code TEXT NOT NULL,
  reviewer_ref TEXT,
  created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  <phase 10 guard columns>
)
```

## Suppression

Suppress by candidate or duplicate group. Recurring same-source/group candidates must not reappear as new.

Suppression rules must be reversible or auditable; do not delete source candidates.

## Tests

Create `tests/test_phase_10_candidate_duplicate_merge.py`.

Assertions:

- duplicate group key stable across replay
- same-source candidate does not create new review noise
- merge preserves source refs from source and target
- suppressed duplicate group hides future reappearing items from normal view
- explicit `--include-hidden` or status view can still show suppressed/merged rows

