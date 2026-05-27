# Phase 03 Entry — V5 Source Location Projection From Registry

## Why

Phase 02 landed the V5 canonical SQLite tables
(`construction_source_locations` + companion sync/run/document tables)
additively, alongside the Phase 01 V2/V3/V4 tables. But no runtime
projection path existed from the YAML-driven `SourceRegistry` into the
V5 `construction_source_locations` table — every read path that wanted
canonical source data had to re-load the YAML registry. Prompt 05 closes
that gap so future Phase 03 work can query V5 directly (e.g.,
`construction_source_sync_state` × `construction_source_locations` joins).

Read-only against Microsoft 365 throughout. The only side effect is
local SQLite writes to `construction_source_locations`.

## Implementation summary

New module: `src/hb_assistant/construction/source_projection.py`.

Exports:

- `class ProjectedSource(BaseModel)` — per-source outcome
  (`source_id`, `source_scope`, `project_key`, `status`,
  `skip_reason`, `lossy_fields`).
- `class ProjectionReport(BaseModel)` — aggregate outcome
  (`total`, `projected`, `compat_projected`, `skipped`, `by_scope`,
  `items`).
- `def project_registry_to_v5_source_locations(registry, store) -> ProjectionReport`
  — defensive duplicate-source_id precheck, per-source mapping,
  per-call upsert via `ConstructionStore.upsert_source_location`,
  returns the report.

Defense in depth on `read_only`:

1. `SourceLocation.read_only: Literal[True]` (Pydantic model layer).
2. `ConstructionStore.upsert_source_location` raises `ValueError` if
   `read_only` ≠ `True` (store layer).
3. V5 schema `CHECK(read_only = 1)` (database layer).

No CLI change this prompt — per the prompt's #7 guidance, existing
surfaces (`graph sources resolve`, `index status`) aren't natural
homes; a `sources project` CLI would be its own prompt.

## Mapping rules (registry `SourceLocation` → V5 `upsert_source_location`)

| Registry field | V5 column / kwarg | Notes |
|---|---|---|
| `source_key` | `source_id` | Stable identity. |
| `kind` (SourceKind enum) | `source_scope` (string) | Direct string projection. |
| `display_name` | `source_name` | Direct. |
| `source_system` | `source_system` | Inferred from `kind` when null on Phase 01 compat records (V5 enforces `NOT NULL`). |
| `project_key` | `project_key` | Direct (nullable). |
| `project_number`, `project_name`, `tenant_id`, `site_url`, `site_id`, `drive_id`, `folder_item_id`, `library_name`, `list_id`, `local_sync_path`, `sync_mode`, `sync_frequency_minutes`, `enabled` | (same name) | Direct. |
| `root_path` | `folder_path` | Model alias bridge. |
| `folder_web_url` | `folder_web_url` | Direct, **unless** kind is `sharepoint_site_page` and `page_url` is set — then `page_url` → `folder_web_url`. |
| `baseline_policy` | `baseline_policy_json` | `model_dump(mode="json", exclude_none=True)` then JSON via store. |
| `folder_policies` | `folder_policies_json` | Same. |
| `crawl_mode`, `indexing_depth`, `match_status`, `match_confidence`, `review_required`, `baseline` (snapshot) | (no V5 column) | **Lossy by design** — recorded in `ProjectedSource.lossy_fields`; registry remains source of truth. |

`source_system` inference rule for Phase 01 compat records:

- `sharepoint_*` → `sharepoint`
- `onedrive_personal` / `onedrive_personal_root` → `onedrive_personal`
- `onedrive_business_root` → `onedrive_business`
- `onedrive_shared` / `onedrive_shared_library` → `onedrive_shared_libraries`

## Projection report (live seed registry, in-memory tmp DB)

Generated via:

```python
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.construction.source_projection import project_registry_to_v5_source_locations

reg = load_source_registry()
store = ConstructionStore("/tmp/tmp_v5_projection.sqlite")
report = project_registry_to_v5_source_locations(reg, store)
print(report.model_dump_json(indent=2))
```

```json
{
  "total": 14,
  "projected": 11,
  "compat_projected": 3,
  "skipped": 0,
  "by_scope": {
    "sharepoint_site": 2,
    "onedrive_personal": 1,
    "sharepoint_project_drive_folder": 7,
    "sharepoint_site_page": 1,
    "onedrive_business_root": 1,
    "onedrive_personal_root": 1,
    "onedrive_shared_library": 1
  }
}
```

All **14/14** registry sources projected. 3 Phase 01 compat records
(`tropical-sharepoint`, `hilltop-sharepoint`, `bobby-onedrive`) tagged
`compat_projected`; 11 canonical Phase 02 records tagged `projected`.
0 skipped.

### Per-source items (status + lossy fields)

| source_id | source_scope | status | lossy_fields |
|---|---|---|---|
| `tropical-sharepoint` | `sharepoint_site` | compat_projected | (none) |
| `hilltop-sharepoint` | `sharepoint_site` | compat_projected | (none) |
| `bobby-onedrive` | `onedrive_personal` | compat_projected | (none) |
| `sp_2023projects_23_435_01_tropical_sl` | `sharepoint_project_drive_folder` | projected | `baseline_snapshot` |
| `sp_2025projects_25_264_01_atlantic_fields_club_core` | `sharepoint_project_drive_folder` | projected | `match_status, match_confidence` |
| `sp_2022projects_22_112_01_pga_the_modern_garage` | `sharepoint_project_drive_folder` | projected | `match_status, match_confidence` |
| `sp_2024projects_24_606_01_alton_hilltop_pbg` | `sharepoint_project_drive_folder` | projected | `match_status, match_confidence` |
| `sp_2025projects_25_244_01_the_wellington` | `sharepoint_project_drive_folder` | projected | `match_status, match_confidence` |
| `sp_2026projects_26_727_01_wellington_marketplace_condo_hotel` | `sharepoint_project_drive_folder` | projected | `match_status, match_confidence, review_required` |
| `sp_2026projects_26_898_01_wellington_townhomes` | `sharepoint_project_drive_folder` | projected | `match_status, match_confidence, review_required` |
| `sp_hilltop_gardens_projecthome` | `sharepoint_site_page` | projected | `crawl_mode, indexing_depth` |
| `od_business_bobby_hedrickbrothers` | `onedrive_business_root` | projected | (none) |
| `od_personal_bobby` | `onedrive_personal_root` | projected | (none) |
| `od_shared_libraries_cloudtemp` | `onedrive_shared_library` | projected | (none) |

### Tropical V5 row (sample post-projection — `get_source_location`)

```json
{
  "source_id": "sp_2023projects_23_435_01_tropical_sl",
  "source_system": "sharepoint",
  "source_scope": "sharepoint_project_drive_folder",
  "source_name": "23-435-01 Tropical - S L",
  "project_key": "tropical",
  "project_number": "23-435-01",
  "project_name": "Tropical - S L",
  "tenant_id": "0e834bd7-628b-42c8-b9ec-ecebc9719be4",
  "site_url": "https://hedrickbrotherscom.sharepoint.com/sites/2023Projects",
  "site_id": "b1abbdda-da3b-4fd1-a038-c4aeb13ba951",
  "drive_id": "b!2r2rsTva0U-gOMSusTupUT0Ecgn6KG9CrTXQO7ex9-wjlyM1iYsETbs3ktNIMr0B",
  "folder_item_id": "01KUIR4CV3RKZL4MURNRKY6DWASR3B7EGM",
  "folder_path": "/23-435-01Tropical -S L",
  "folder_web_url": "https://hedrickbrotherscom.sharepoint.com/sites/2023Projects/Shared%20Documents/23-435-01Tropical%20-S%20L",
  "library_name": "Shared Documents",
  "list_id": "35239723-8b89-4d04-bb37-92d34832bd01",
  "sync_mode": "graph_delta",
  "sync_frequency_minutes": 30,
  "enabled": true,
  "read_only": true,
  "baseline_policy": {
    "mode": "shallow_metadata_first",
    "deep_index_default": false,
    "classify_project_matches": false,
    "graph_delta_required": true,
    "require_review_for_sensitive": false,
    "policy_tags": []
  },
  "folder_policies": {
    "deep_index_allowed": ["07-RFI", "15-Submittal", "06-Meeting", "09-DailyReport", "21-Potential Delays"],
    "metadata_only": ["00-Est", "12-Accounting", "13-ChangeOrder", "19-Monthly Forecast", "16-DrawSpecPic", "22-Aerials", "14-Subcontractor"],
    "review_required": ["00-Est", "12-Accounting", "13-ChangeOrder", "19-Monthly Forecast", "contracts", "change orders", "financial reports"]
  }
}
```

baseline_policy + folder_policies round-trip through JSON without loss.

### Hilltop Gardens ProjectHome (page_url → folder_web_url)

```json
{
  "source_id": "sp_hilltop_gardens_projecthome",
  "source_scope": "sharepoint_site_page",
  "site_url": "https://hedrickbrotherscom.sharepoint.com/sites/HilltopGardens",
  "folder_web_url": "https://hedrickbrotherscom.sharepoint.com/sites/HilltopGardens/SitePages/ProjectHome.aspx"
}
```

V5 has no `page_url` column; the page URL lands in `folder_web_url`
so it remains reachable from a V5 row. `crawl_mode` and
`indexing_depth` are not represented in V5 (recorded as
`lossy_fields`).

## Test results

```
$ python -m pytest tests/test_construction_sources.py tests/test_construction_store_repositories.py
80 passed in 0.64s
```

Includes 8 new tests in `tests/test_construction_sources.py`:

1. `test_v5_projection_covers_all_14_registry_sources` — 14/14 land.
2. `test_v5_projection_uses_source_key_as_source_id` — identity preserved.
3. `test_v5_projection_marks_legacy_compat_sources` — 3 compat records tagged.
4. `test_v5_projection_rejects_duplicate_source_id` — defensive precheck raises.
5. `test_v5_projection_rejects_read_only_false` — store-layer guard intact.
6. `test_v5_projection_round_trips_baseline_and_folder_policies` — JSON round-trip.
7. `test_v5_projection_maps_sharepoint_site_page_page_url_to_folder_web_url` — Hilltop page URL preserved.
8. `test_v5_projection_infers_source_system_for_legacy_compat_records` — inference rule.

All existing tests (registry shape, V2 source resolutions, V5 migration shape, store repository round-trips) still pass — the projection was added strictly additively.

## Compatibility statement

- **V2/V3/V4 tables**: unchanged. `construction_source_resolutions`,
  `construction_delta_tokens`, `construction_drive_item_inventory`,
  `construction_crawl_receipts`, `construction_review_queue`,
  `construction_model_decisions` are untouched.
- **Existing tests**: still pass.
  `tests/test_construction_store_repositories.py::test_v5_migration_is_additive_v2_v3_v4_intact`
  in particular confirms V5 additions did not invalidate V2/V3/V4 schema.
- **Internal field names**: no rename of `source_key` → `source_id` in
  source code. The model continues to expose both names via Pydantic
  aliases. The projection function is the sole place that translates
  the names — and only at the call boundary into the V5 store.
- **CLI surface**: unchanged. `graph delta`, `graph sources resolve`,
  `graph auth status`, `index status`, `validate`, `sources validate`
  all behave identically.
- **No source-system writeback**: confirmed by code path
  (`ConstructionStore.upsert_source_location` is a local SQLite write
  only; no HTTP client, no Graph call, no file I/O outside the DB).

## Guardrail attestation

- [x] V5 projection works (14/14 sources land).
- [x] V2/V3/V4 compatibility intact (existing 80 tests still pass).
- [x] No source-system writes (no Graph or filesystem mutation).
- [x] `read_only=False` rejected at three layers (model, store, schema CHECK).
- [x] `baseline_policy` and `folder_policies` round-trip deterministically.
- [x] Phase 01 compat records explicitly tagged (`status=compat_projected`).
- [x] Lossy fields documented per source (`crawl_mode`, `indexing_depth`,
      `match_status`, `match_confidence`, `review_required`,
      `baseline` snapshot — none of which V5 represents).
- [x] No CLI change this prompt; no `source_key` → `source_id` rename.
