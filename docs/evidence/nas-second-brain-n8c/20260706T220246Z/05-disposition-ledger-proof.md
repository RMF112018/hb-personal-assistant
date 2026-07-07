# 05 — Disposition ledger proof (append-only)

`ReviewRepository.record_disposition` + `review_disposition.py` implement a local/operator disposition
ledger that writes ONLY `assistant_review_dispositions` (+ one `assistant_review_events` row) and never
mutates the review item or any source table.

## Append-only, never upsert
- `disposition_id` folds a per-call `created_at_nonce` (uuid) → every applied disposition is a distinct
  ledger row. `review_item_id` stays deterministic.
- Proof `tests/test_review_repository.py::test_dispositions_are_append_only`: two dispositions on one item
  → 2 distinct `disposition_id`s, 2 ledger rows; a prior decision is never overwritten.

## Overlay-only, executes nothing
- `record_disposition` inserts a disposition + a `disposition_recorded` event; it does not touch
  `assistant_claims`, decision/preference/open-loop records, memory, context-packs, or the vault, and it
  performs no email/calendar/task/reminder/notification/N8D call.
- Proof `test_disposition_does_not_mutate_item_columns`: after `accept`, the review item's built
  `review_state`/`effective_state` columns are unchanged (`unreviewed`/`candidate`) — the disposition is
  the authoritative overlay, read via the effective-state model.

## Read-only preview
- `preview_disposition` / `apply_disposition(apply=False)` compute the resulting state without writing.
  Proof `test_disposition_preview_is_read_only`: 0 ledger rows written on preview.

## Local-only exposure
- Disposition writers are CLI-only (`hb-assistant review disposition --apply`). There is NO API
  disposition route and NO MCP disposition tool (see 09 + 10).
