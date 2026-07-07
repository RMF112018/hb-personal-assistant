# 03 — Schema V106 & Contract

`LATEST_SCHEMA_VERSION` 105 → **106**. Additive only; no existing table touched. All four tables ship
EMPTY; nothing populates them on startup — only an explicit `intelligence build --apply` writes rows.

## Migrator wiring (`store/migrator.py`)

```
17:  LATEST_SCHEMA_VERSION = 106
6990: def _v106_statements() -> list[str]:
6991:     from hb_assistant.store.assistant_intelligence_projection_tables import V106_STATEMENTS
6993:     return V106_STATEMENTS
8774: # v106 (NAS N8C-10): review-aware intelligence projections — guarded, additive, empty on create
8784:     for stmt in self._v106_statements(): ...
8787:     INSERT INTO schema_migrations (version, name, applied_at)
8787:       VALUES (106, 'v106_assistant_intelligence_projection', ?)
```

The V106 block is guarded by `SELECT version FROM schema_migrations WHERE version = 106` (mirrors the
V100–V105 blocks), so it applies exactly once and re-running the migrator is idempotent.

## Four projection-owned tables (`store/assistant_intelligence_projection_tables.py`)

1. **`assistant_intelligence_projections`** — header: `projection_id` PK, `projection_type` (enum CHECK),
   `title`, `objective`, `scope_json`, `filter_policy_json`, `budget_json`, `status` (enum CHECK, default
   `draft`), `input_digest`, `output_digest`, `trusted/candidate/excluded/stale/superseded/item` counts,
   `truncated` (0/1 CHECK), `created_by`, `created_at`/`updated_at`, `metadata_json`. Indexes on
   `(projection_type, status)` and `(input_digest)`.
2. **`assistant_intelligence_projection_items`** — `projection_item_id` PK, `projection_id`, `item_order`,
   `target_kind` (enum CHECK), `target_id` NOT NULL, `review_item_id`, `disposition_id`, `effective_state`
   (nullable enum CHECK), `inclusion_state` (enum CHECK), `review_state` (nullable enum CHECK), bounded
   `title`/`summary`/`evidence_excerpt`, the 12 provenance anchors + 3 digests, `confidence` (0..1 CHECK),
   `priority`, `token_estimate`, `included` (0/1 CHECK), `exclusion_reason`, `created_at`, `metadata_json`.
   **Provenance CHECK: ≥1 of the 12 anchors must be non-NULL** (in addition to `target_id NOT NULL`).
3. **`assistant_intelligence_projection_receipts`** — `projection_receipt_id` PK, `projection_id`,
   `builder_version`, `input_digest`, `output_digest`, `filter_policy_json`, `budget_json`, the 5 counts +
   `dropped_count`, `truncated` (0/1 CHECK), `created_at`, `metadata_json`.
4. **`assistant_intelligence_projection_events`** — append-only lifecycle log: `event_id` PK,
   `projection_id`, `event_type` (enum CHECK ∈ created/built/exported/marked_stale/marked_superseded/
   failed), `from_status`, `to_status`, `detail`, `created_at`. **Lifecycle only — NOT a bridge/job
   execution event system.**

## Enum single-source-of-truth (no drift)

The V106 module **re-uses** `EFFECTIVE_STATE_VALUES`, `REVIEW_STATE_VALUES`, `REVIEW_TARGET_KIND_VALUES`
from `assistant_review_tables` (N8C-9) for the item CHECKs, so the projection layer can never drift from the
review overlay it reads. `intelligence_projection_models.py` in turn re-exports `PROJECTION_TYPE_VALUES`,
`PROJECTION_STATUS_VALUES`, `INCLUSION_STATE_VALUES`, `PROJECTION_EVENT_TYPE_VALUES` from the schema module,
so the DB CHECK and the Python validation share one definition.

## Enums

- `projection_type`: trusted_context, candidate_context, review_aware_context, implementation_context,
  project_intelligence, decision_memory_context, open_loop_context, daily_brief_context, unknown.
- `status`: draft, built, stale, superseded, failed.
- `inclusion_state`: trusted, candidate, excluded, stale, superseded, not_required, deferred, unknown.
- `event_type`: created, built, exported, marked_stale, marked_superseded, failed.

## Migration test proof

`tests/test_intelligence_projection_v106_migration.py` (5 tests, green): head == 106; the four tables
exist; migrate is idempotent (re-apply is a no-op); V100–V105 migration rows survive; an item insert with
`target_id` set but every provenance anchor NULL is rejected by the provenance CHECK.
