# Phase 04B Prompt 02 — History Recording Repository + Diff Engine

**Date:** 2026-05-29 · **Module:** `src/hb_assistant/store/procore_history.py` ·
**Wiring:** `src/hb_assistant/procore/live_sync.py`.

## Summary

Implements the persistence logic that turns each current-state Procore upsert into historical memory:
per-record **snapshots**, field-level **change events**, and assistant-ready **timeline events**,
driven by a canonical-hash comparison and a generic **diff engine**. Writes into the V7 history tables
alongside the existing `procore_live_records` latest-state table, which is **unchanged**. No schema
change, no live calls (tests use the fake transport).

## Sync flow (per normalized record, in `live_sync.run_live_sync`)

After the existing latest-state `upsert_procore_live_record`, the orchestrator calls
`record_procore_history_for_record(...)` in its own guard (a history failure never breaks
latest-state), which runs:

```
current-state lookup (state_index)
 -> compute_canonical_hash + compare to current
 -> snapshot insert if new/changed        (procore_live_record_snapshots)
 -> change events if changed               (procore_live_record_change_events)
 -> timeline events for significant changes (procore_record_timeline_events)
 -> current-state upsert                    (procore_live_record_state_index)
```

## Public API (`procore_history.py`)

| function | role |
|---|---|
| `compute_canonical_hash(fields)` | SHA-256 of sorted-key canonical JSON (matches the upsert serialization) |
| `ChangeEvent` (dataclass) | field_path, change_type, change_category, old/new_value_redacted, old/new_value_hash, importance, review_required, significant |
| `diff_canonical_records(prev, cur)` | recursive dotted-path diff; nested dicts; lists of dicts diffed by stable id; `*_summary` treated atomically |
| `record_procore_snapshot_if_changed(...)` | inserts a snapshot iff the hash differs; returns previous canonical for diffing |
| `record_procore_change_events(...)` | persists field-level change rows |
| `record_procore_timeline_events(...)` | persists timeline rows for `significant` events only |
| `record_procore_current_state(...)` | upserts the state-index row (latest hash + last seen/changed) |
| `record_procore_history_for_record(...)` | sync-flow wrapper running the full sequence above |
| `get_procore_record_history(record_key)` | snapshots oldest-first — full reconstruction |
| `get_procore_changes(project_key, since_utc=...)` | change events by project + time window — last-48h queries |

## Change categories

All required categories are classified by field path + value transition: `record_created`,
`status_changed` / `closed` / `reopened` (status token transitions), `became_overdue`,
`due_date_changed`, `assignee_changed`, `ball_in_court_changed`, `priority_changed`, `response_added`,
`attachment_added`, `text_changed`, `cost_impact_changed`, `schedule_impact_changed`,
`inspection_item_response_changed`, `inspection_item_became_unanswered`,
`inspection_item_became_deficient` (plus a `field_changed` catch-all). The significant subset drives
timeline events.

## Guardrails / redaction

- Inputs are the **already-redacted** canonical-field dicts (free text → `*_summary` hash blocks,
  people → hashed entities). The diff additionally reduces any dict / list / string > 120 chars to a
  **hash only** (`_value_repr`); only short scalars (status, dates, opaque ids, numbers) are kept
  verbatim in `*_value_redacted`. `*_summary` blocks are diffed atomically as `text_changed` and never
  expanded.
- Timeline `summary_redacted` is `"{category} ({field_path})"` — canonical key names only, never raw
  text.
- All history rows carry `raw_body_persisted = 0` (schema CHECK); snapshots/state also
  `redaction_applied = 1`.
- **Idempotent:** snapshot / change / timeline ids are deterministic (SHA-256 of record_key + hashes +
  field_path) and every insert is `INSERT OR IGNORE`; unchanged re-syncs short-circuit on the hash
  match. Re-running an identical (even identically-changed) sync records no duplicate history.

## Tests

- `tests/test_procore_history_diff.py` (unit): order-independent hash; scalar/nested/keyed-array diffs;
  status closed/reopened; became_overdue; response/attachment added; inspection-item categories;
  `*_summary` + long-string values stored hash-only; short scalars kept verbatim; significant flags.
- `tests/test_procore_history_sync_flow.py` (integration via fake transport): first sync → state row +
  1 snapshot + `record_created` event; unchanged re-sync → no duplicate snapshot (and latest-state
  still one row); changed sync (open→closed) → +1 snapshot + `closed` change event + `closed` timeline
  event; `get_procore_record_history` returns 2 ordered snapshots (reconstruction);
  `get_procore_changes(since)` returns the changes and respects the time window.

## Acceptance

- **Full history reconstructable** — `get_procore_record_history` returns ordered snapshots, each with
  redacted canonical JSON.
- **Last-48h changes answerable** — `get_procore_changes(project_key, since_utc=now-48h)` returns the
  field-level change events.
- **Current-state upsert remains idempotent** — `procore_live_records` row count is unchanged across
  re-syncs; `procore_live_records` behavior untouched.

## Validation

```
python -m pytest -q --no-header   # full suite green (2 pre-existing skips)
ruff check .                      # All checks passed
mypy .                            # Success: no issues found in 190 source files
python -m compileall src tests    # OK
```
