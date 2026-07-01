# Phase 17 Repo-Truth Audit

Base: `d4220fce` (Phases 15 + 16 merged on `origin/main`).

## Schema inventory (pre-V98)

### Standard review path (V91/V92)

| Object | Purpose |
|--------|---------|
| `project_schedule_review_items` | Persisted review queue keyed by `(project_key, schedule_version_key, stable_item_key)` |
| `idx_project_schedule_review_items_version_key` | Unique dedupe index |
| `idx_project_schedule_review_items_project_status` | Status filter |
| `idx_project_schedule_review_items_stable_key` | Carry-forward lookup |
| `project_schedule_review_item_events` | Audit: `created`, `synced`, `status_changed`, `notes_changed`, `carried_forward` |

Columns: `review_status` CHECK `('open','reviewed','dismissed','watching')` — no `disposition_reason`.

### Named-baseline review path (V97)

| Object | Purpose |
|--------|---------|
| `project_schedule_named_baseline_review_items` | Parallel persistence for named-baseline workbench |
| `idx_ps_named_baseline_review_identity` | Unique dedupe on scope + source keys |
| `project_schedule_named_baseline_review_item_events` | Audit (no `carried_forward`) |

Same four legacy `review_status` values.

## Audit answers (12 questions)

1. **Persistence exists?** Yes — V91 items + V92 events; V97 named-baseline parallel tables.
2. **Dispositions?** Legacy four only (`open`, `watching`, `reviewed`, `dismissed`).
3. **Operator-gated writes?** Yes — `require_operator_role` on POST sync and PATCH.
4. **Audit trail?** Yes — event rows on create/sync/status/notes/carry-forward.
5. **Preview → persisted today?** Bulk POST sync materializes all materializable cues; no selective promote.
6. **Dedup?** Unique indexes prevent duplicate rows per stable identity.
7. **Driver/comparison tied to status?** Driver detail exposes read-only disposition fields; not Phase 17 taxonomy.
8. **Hub/Controls rollups?** Legacy `open_count`/`watching_count` only; no Phase 17 rollup read model.
9. **Export review disposition?** `## Review Workbench` item list with legacy statuses; no rollup section.
10. **Raw IDs in PM payloads?** Phase 16 redaction via `include_technical`; some operator paths still expose version keys.
11. **Frontend action loop?** Workbench auto-POST-syncs on load; per-item legacy status dropdown + PM notes PATCH.
12. **Gaps** — Phase 17 dispositions, selective promote, reason-required backend validation, rollups, export section, preview/persisted UX separation.

## V98 migration strategy

### Goals

- Store **canonical** Phase 17 dispositions in `review_status` going forward.
- Accept legacy aliases on read/write only (`open`→`needs_review`, etc.).
- Add `disposition_reason TEXT` to both item tables.
- Extend event CHECK to include `promoted`; add `disposition_reason` on events.
- **Preserve all rows**, indexes, and event history.

### Data migration mapping

| Legacy | Canonical |
|--------|-----------|
| `open` | `needs_review` |
| `watching` | `needs_review` |
| `reviewed` | `accepted_for_follow_up` |
| `dismissed` | `dismissed_not_material` |

### Execution (per table)

1. `CREATE TABLE …_v98` with expanded CHECK + `disposition_reason`.
2. `INSERT … SELECT` with `CASE` status mapping; `disposition_reason` NULL for migrated rows.
3. `DROP` old table; `RENAME` new table; recreate indexes verbatim.
4. Events tables: rebuild CHECK to add `promoted`; add `disposition_reason` column via rebuild.

### Idempotent promotion (post-migration)

- `upsert_review_item(..., emit_sync_event=False)` when row already exists during promote.
- Second promote returns existing row; **no** `synced` or `promoted` event.

### Rollback posture

- Migration is forward-only; rollback requires restoring DB backup (documented in limitations).
