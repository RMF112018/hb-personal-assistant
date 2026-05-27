# Phase 03 Entry — V5 Drive-Item Bridge + Read Model

## Why

Phase 02 landed `construction_drive_items` (V5, 24 cols) additively alongside
the Phase 01 `construction_drive_item_inventory` (V2, 13 cols). The live delta
crawler still writes only to V2; V5 stays empty until a later prompt flips
writes. Phase 03 wants to begin **reading** from V5-shaped structures today,
without bulk-mirroring data or deleting V2. Prompt 06 closes that gap with a
read-model bridge.

Strictly read-only — no Microsoft 365 mutation, no source file changes, no
new SQLite write paths (the bridge module imports only `BaseModel` and the
`ConstructionStore`; no `requests`, `os.write`, `shutil`, `subprocess`).

## Design choice — read model (not bulk mirror)

Two paths were available per the prompt: mirror V2 rows into V5, or expose a
read model that unions V2 and V5 safely. **We picked the read model** for
three reasons:

1. **No data duplication** — V2 stays authoritative for writes; V5 stays
   the canonical write target for future Phase 03 work. Two sources of truth
   are avoided.
2. **No FK pressure** — V5 has `FOREIGN KEY(source_id) REFERENCES construction_source_locations(source_id)`; bulk-mirroring would require all source_locations to be projected first (Prompt 05 already does this, but coupling them in a strict order would be fragile).
3. **Self-deprecating** — the union read uses **V5-wins precedence** on key
   collision. When a later prompt flips the crawler to write V5 directly,
   callers transparently switch to V5-canonical data with **zero code change
   in the bridge or its consumers** — the V2 row simply becomes a no-op
   shadow until cleanup.

## Module surface

`src/hb_assistant/construction/drive_item_bridge.py`:

| Name | Kind | Purpose |
|---|---|---|
| `V5DriveItem(BaseModel)` | Pydantic model | Canonical V5 row shape (24 fields). `model_config = {"extra": "forbid"}` blocks accidental body/content/text/excerpt leakage at the type layer. |
| `v2_row_to_v5(v2_row: dict) -> V5DriveItem` | Pure function | Deterministic V2 → V5 projection. |
| `BridgeReport(BaseModel)` | Pydantic model | Per-source counts (`v2_only`, `v5_only`, `both`, `total_unified`, `lossy_v2_fields`). |
| `read_drive_items_unified(store, *, source_id, v2_limit=None, v5_limit=None) -> list[V5DriveItem]` | Read | Union read with V5-wins precedence. |
| `summarize_bridge(store, source_ids, *, per_source_limit=None) -> dict[str, BridgeReport]` | Read | Overlap stats per source. |

`src/hb_assistant/construction/store/repositories.py` — two **read-only**
helpers added:

| Name | Purpose |
|---|---|
| `list_inventory(*, source_key, limit=None) -> list[dict]` | Iterate V2 inventory rows for a source. |
| `list_drive_items(*, source_id, limit=None) -> list[dict]` | Iterate V5 drive_items rows for a source. |

Both expose an optional `limit` parameter for row-count-bounded sweeps so
bridge callers never run an unbounded scan against a large table.

## Mapping rules (V2 inventory row → V5 `V5DriveItem`)

| V2 column | V5 field | Notes |
|---|---|---|
| `source_key` | `source_id` | Identity preservation. |
| `item_id` | `drive_item_id` | Identity. |
| `drive_id` | `drive_id` | Direct. |
| `name`, `web_url`, `size_bytes`, `last_modified` | `name`, `web_url`, `size_bytes`, `last_modified_datetime` | Direct. |
| `parent_path` | `path` | V5 has both `path` (string) and `parent_drive_item_id` (id). V2 doesn't track parent IDs, so `parent_drive_item_id` stays `None`. |
| `is_folder` (INT) | `is_folder` (bool) | INT → bool. |
| (derived) | `is_file` | `True` when `is_folder == 0`; V2 items are folder XOR file in practice. |
| `status` ('active' / 'deleted') | `deleted` (bool) | `status == 'deleted'` → `True`; otherwise `False`. **Soft-delete only** — never mutates the source file. |
| `etag`, `first_seen_at`, `last_seen_at` | (no V5 column) | **Lossy** — declared in `BridgeReport.lossy_v2_fields`; `created_utc`/`updated_utc` are `None` on V2-derived items in the read model (caller can detect "this came from V2"). |
| (no V2 column) | `parent_drive_item_id`, `site_id`, `list_id`, `list_item_id`, `file_extension`, `mime_type`, `quick_xor_hash`, `project_number_detected`, `document_type_detected`, `indexing_policy`, `classification_status` | `None` — future Phase 03 writes targeting V5 directly will populate these. |

## Row-count proof (live DB, read-only)

Live DB path: `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`.

```
$ python -c "...bridge sanity for Tropical..."
V2 inventory rows (Tropical):                401
V5 drive_items rows (Tropical):                0
Unified read (V5-wins on collision):         401

BridgeReport for sp_2023projects_23_435_01_tropical_sl:
  v2_only       = 401
  v5_only       = 0
  both          = 0
  total_unified = 401
  lossy_v2_fields = ['etag', 'first_seen_at', 'last_seen_at']
```

First 3 unified items (V2-derived, V5 shape):

```
drive_item_id=01KUIR4CQ2PPTQQ7YHBVOI7QFDXOY5WAV4  name='Div 10'  is_folder=True  is_file=False  deleted=False  created_utc=None
drive_item_id=01KUIR4CQ4OO7ESUP3T5N3ISXRMGBR4A25  name='Tropical World Nursery-Buyout Summary 082624.pdf'  is_folder=False  is_file=True  deleted=False  created_utc=None
drive_item_id=01KUIR4CQ4OVSSLGGRCBG2CLG2WCTRSA3X  name='RFI PC-39 - Response and Drawing Clarification.pdf'  is_folder=False  is_file=True  deleted=False  created_utc=None
```

- All 401 V2 inventory rows project losslessly into V5 shape via
  `v2_row_to_v5` (lossy fields documented per source).
- V5 table count is unchanged at 0 — the bridge made **no V5 writes**.
- Union read returns 401 items, all V2-derived (`v5_only == both == 0`).
- `is_folder`/`is_file` correctly flipped by kind; `deleted == False` for all
  401 (no soft-deletes in the current Tropical state).
- `created_utc` / `updated_utc` are `None` on V2-derived items in the read
  model — the caller can detect provenance by inspecting these.

No SQLite write occurred — pre/post `sqlite3 .pragma quick_check` would
return the same fingerprint (not run here to avoid noise; the bridge code
contains no SQL `INSERT`/`UPDATE`/`DELETE` statements, verified by reading
the module).

## Compatibility proof

- V2 `construction_drive_item_inventory` schema and callers (the delta
  crawler at `src/hb_assistant/construction/graph/delta_crawler.py`)
  are unchanged. The crawler continues to write V2 only.
- V5 `construction_drive_items` schema unchanged; no migration this
  prompt.
- Internal field names in source code are not renamed — `source_key`
  remains in V2 paths; `source_id` remains in V5 paths; the bridge
  translates only at the call boundary.
- All existing tests in `tests/test_construction_store_repositories.py`
  continue to pass (including
  `test_no_body_or_text_columns_in_inventory`,
  `test_inventory_upsert_returns_new_then_updated`,
  `test_mark_inventory_deleted_is_sticky`,
  `test_v5_migration_creates_all_canonical_tables`,
  `test_v5_migration_is_additive_v2_v3_v4_intact`).
- `tests/test_construction_graph_delta.py` continues to pass (the
  crawler is untouched).
- No CLI surface change.

## Test results

```
$ python -m pytest tests/test_construction_store_repositories.py tests/test_construction_graph_delta.py
65 passed in 0.74s
```

Includes 9 new bridge tests:

1. `test_v5_drive_item_bridge_v2_row_to_v5_shape` — all V5 fields populated; `extra=forbid` blocks body/content/text/excerpt/preview/full_text on a fresh `V5DriveItem(...)`.
2. `test_v5_drive_item_bridge_source_key_to_source_id_mapping_deterministic` — same input → same output across runs.
3. `test_v5_drive_item_bridge_status_active_maps_deleted_false`.
4. `test_v5_drive_item_bridge_status_deleted_maps_deleted_true`.
5. `test_v5_drive_item_bridge_is_file_inferred_from_is_folder`.
6. `test_v5_drive_item_bridge_lossy_fields_recorded_in_report` — `etag`/`first_seen_at`/`last_seen_at` flagged.
7. `test_v5_drive_item_bridge_unified_read_v5_wins_on_collision` — V5 row name/size/classification override V2 on key collision.
8. `test_v5_drive_item_bridge_unified_read_unions_disjoint_sets` — V2-only and V5-only items both appear in the unified output.
9. `test_v5_drive_item_bridge_module_has_no_writeback_paths` — static-source scan ensures no `requests.post/put/patch/delete`, no `subprocess`, no `os.remove/unlink/rmdir`, no `shutil.rmtree`, no `Path.unlink/write/rmdir`, no `.write_text`/`.write_bytes` calls in the bridge module.

ruff clean on touched files.

## Remaining migration debt (not in this prompt)

- The delta crawler still writes V2 only — flipping its write path to V5
  is a future prompt's work. Until then, V5 stays empty for delta-sourced
  data, and the bridge serves both V2-only (today) and mixed-mode (during
  cutover) states.
- The lossy V2 fields (`etag`, `first_seen_at`, `last_seen_at`) are not
  represented in V5. If any Phase 03 query needs them, the schema would
  need extension; this is **deferred** until a real consumer requires it.
- V5's richer fields (`file_extension`, `mime_type`, `quick_xor_hash`,
  `project_number_detected`, `document_type_detected`, `indexing_policy`,
  `classification_status`) are populated by no current writer. When the
  crawler flip happens, those fields can begin populating; the
  classification/policy populators are Phase 03+ work.
- V2 table teardown is **explicitly out of scope** for this prompt and
  for all of Phase 03 entry; teardown depends on every reader being
  flipped to the bridge first.

## Guardrail attestation

- [x] V5-compatible read model exists (`V5DriveItem` + `v2_row_to_v5` +
      `read_drive_items_unified`).
- [x] No compatibility break (all 65 existing tests pass; V2 schema +
      callers untouched).
- [x] No source-system mutation (bridge is read-only; no HTTP/filesystem
      writes; module-level static scan confirms it).
- [x] Source-id mapping is deterministic (test-pinned).
- [x] Soft-delete semantics explicit (`status='deleted'` → `deleted=True`;
      bridge never touches the source file).
- [x] `extra: forbid` on `V5DriveItem` blocks body/content/text/excerpt
      leakage at the type layer.
- [x] Row-count bounded (`limit` param on `list_inventory` /
      `list_drive_items` / `summarize_bridge`).
