# Phase 17 Review API Audit

## Endpoints

| Method | Path | Role | Notes |
|--------|------|------|-------|
| GET | `/schedule/review-items` | viewer+ | Preview + persisted merge; includes `workbench.review_status` rollup |
| POST | `/schedule/review-items` | operator | Legacy bulk sync retained |
| POST | `/schedule/review-items/promote` | operator | Selective idempotent promotion by `stable_item_keys` |
| PATCH | `/schedule/review-items/{id}` | operator | Accepts `disposition`/`review_status`, `disposition_reason`, `pm_notes`; project scope enforced |
| GET | `/schedule/review-items/{id}/events` | viewer+ | Unchanged |

## Backend enforcement

- `validate_disposition_change()` on every PATCH
- `disposition_reason_required` for dismiss/supersede/duplicate/resolved
- `operator_disposition_not_allowed` for `blocked_by_*`
- `review_item_project_mismatch` when project_key does not match row
- Trust context from `review_trust_context()` blocks clearing system-blocked dispositions

## Promotion idempotency

- Pre-check `get_review_item_for_version_scope` / `get_by_identity`
- Existing row: skip upsert events (`emit_sync_event=False`)
- New row: `EVENT_PROMOTED` (named) or `EVENT_PROMOTED`/`EVENT_CREATED` (standard)
