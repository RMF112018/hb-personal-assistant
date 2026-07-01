# Phase 13 Persistence Design

**Proof type:** repo truth  
**Timestamp:** 2026-07-01T09:04:10Z

## Strategy: separate table (V97)

**Table:** `project_schedule_named_baseline_review_items`  
**Events:** `project_schedule_named_baseline_review_item_events`

`project_schedule_review_items` is **unchanged**. prior_update unique index remains intact.

### Rationale

1. Unique index audit: `idx_project_schedule_review_items_version_key` is droppable, but extending the existing table would require changing all upsert/list/carry-forward paths used by prior_update.
2. Amendment 2: prefer separate table unless extend is proven necessary — separate table maximizes prior_update isolation.
3. Amendment 4: named persistence uses **only** scoped repository methods; no `get_latest_review_item_by_stable_key` for named items.

## Identity key (named_baseline)

Minimum scope (all persisted rows):

```
project_key
current_schedule_version_key
review_scope = 'named_baseline'
comparison_basis (= baseline_slot_key)
baseline_schedule_version_key
source_stable_key
source_metric_key
source_signal_type
COALESCE(source_activity_id, '')
```

**Unique index:** `idx_ps_named_baseline_review_identity` on the columns above.

**Item IDs:** `psnbri-{uuid}` (distinct from `psri-` prior_update IDs)

### Traceability columns

- `baseline_slot_label`, `baseline_selection_id`, `baseline_schedule_data_date`, `baseline_display_name`
- `schedule_data_date`, `as_of_date`
- `evidence_json` includes cue lineage fields

## Carry-forward rules

| Transition | Behavior |
|------------|----------|
| prior_update ↔ named | No carry (separate tables) |
| named slot A ↔ named slot B | No carry (comparison_basis filter) |
| same slot, different baseline_schedule_version_key | No carry (baseline version in identity) |
| same slot + same baseline version + same current schedule | Rehydrate on GET/sync |

Clearing a slot does not delete historical rows; queries filter to active baseline context only.

## Events/audit

Separate events table keyed by `review_item_id`. Event types mirror prior_update: `created`, `synced`, `status_changed`, `notes_changed`.

PATCH and GET events route by `psnbri-` prefix.

## Migration V97

- **Version:** 97 (`v97_project_schedule_named_baseline_review_items`)
- **Type:** additive CREATE TABLE + indexes
- **Rollback:** restore pre-phase13 backup (forward-only; no down migration)

## Rehearsal plan

1. Copy real DB to `/tmp/phase13-rehearsal.sqlite`
2. Run migrator to v97
3. `PRAGMA integrity_check`
4. Verify `project_schedule_review_items` row count and indexes unchanged
5. Apply to real DB only after rehearsal passes

## API contract additions

POST sync response:
```json
{
  "synced": true,
  "review_scope": "named_baseline",
  "comparison_basis": "current_contract_baseline",
  "baseline_context": { ... }
}
```

GET returns merged persisted + unsynced live candidates in named scope.
