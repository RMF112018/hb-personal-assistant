# Phase 03 Entry — Tropical Limited Local Apply + SQLite Receipt

## Why

Prompt 03 (commit `a24a89d`) proved the folder-scoped Graph delta endpoint
works for Tropical in `dry_run` mode. Prompt 04 exercises the `--apply`
path with the same 2-page cap and proves local SQLite persistence,
receipt handling, and raw delta-link containment. Strictly read-only on
Microsoft 365; writes confined to the local construction SQLite tables.

## Pre-apply SQLite snapshot

DB path: `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite` (outside repo, app-support local-only).

```sql
SELECT 'inventory'      AS tbl, COUNT(*) FROM construction_drive_item_inventory WHERE source_key='sp_2023projects_23_435_01_tropical_sl'
UNION ALL
SELECT 'delta_tokens'   AS tbl, COUNT(*) FROM construction_delta_tokens         WHERE source_key='sp_2023projects_23_435_01_tropical_sl'
UNION ALL
SELECT 'crawl_receipts' AS tbl, COUNT(*) FROM construction_crawl_receipts       WHERE source_key='sp_2023projects_23_435_01_tropical_sl';
```

| Table | Pre-apply rows |
|---|---|
| `construction_drive_item_inventory` | 0 |
| `construction_delta_tokens` | 0 |
| `construction_crawl_receipts` | 0 |

## Command

```bash
hb-assistant construction-agent graph delta \
  --source sp_2023projects_23_435_01_tropical_sl \
  --apply \
  --max-pages 2 \
  --json
```

Exit code: `0`.

## Verbatim CLI JSON receipt (sample_items truncated to 5)

```json
{
  "command": "construction-agent graph delta",
  "source": "sp_2023projects_23_435_01_tropical_sl",
  "mode": "apply",
  "status": "ok",
  "receipt": {
    "run_id": "f2d87cc7-5dd5-4b9e-a728-9ac928894414",
    "source_key": "sp_2023projects_23_435_01_tropical_sl",
    "drive_id": "b!2r2rsTva0U-gOMSusTupUT0Ecgn6KG9CrTXQO7ex9-wjlyM1iYsETbs3ktNIMr0B",
    "mode": "apply",
    "status": "ok",
    "started_at": "2026-05-27T23:09:11.143076+00:00",
    "finished_at": "2026-05-27T23:09:13.955598+00:00",
    "pages_seen": 2,
    "items_seen": 416,
    "items_new": 401,
    "items_updated": 15,
    "items_deleted": 0,
    "delta_link_recorded": false,
    "sample_items": [
      {"id": "01KUIR4CV3RKZL4MURNRKY6DWASR3B7EGM", "name": "23-435-01Tropical -S L", "is_folder": true,  "size": 39785583704, "last_modified": "2025-01-08T14:08:53Z", "deleted": false},
      {"id": "01KUIR4CSMRP6OKDFAKJPKVS7GLOWLXPL5", "name": "00-Est",                  "is_folder": true,  "size":  8117226290, "last_modified": "2024-09-23T16:14:30Z", "deleted": false},
      {"id": "01KUIR4CQUII4Y3YUMXBPI2W2TC36VKWES", "name": "00 Precon Agreement",    "is_folder": true,  "size":      428428, "last_modified": "2024-08-07T10:52:33Z", "deleted": false},
      {"id": "01KUIR4CTOP72BRXRLOBPJH5APR6DAMZOX", "name": "Hedrick Brothers - Precon Letter- Boynton beach Tropical.docx", "is_folder": false, "size": 206658, "last_modified": "2023-12-14T20:30:30Z", "deleted": false},
      {"id": "01KUIR4CRUGOZROBOWFZKLHORM37N4YXZW", "name": "Hedrick Brothers - Precon Letter- Boynton Beach Tropical.pdf",  "is_folder": false, "size": 221770, "last_modified": "2023-12-14T19:10:23Z", "deleted": false}
    ],
    "error_redacted": null,
    "scope": "sharepoint_project_drive_folder",
    "endpoint_kind": "folder_scoped",
    "folder_item_id": "01KUIR4CV3RKZL4MURNRKY6DWASR3B7EGM",
    "baseline_comparison": {
      "source_key": "sp_2023projects_23_435_01_tropical_sl",
      "project_key": "tropical",
      "scope": "sharepoint_project_drive_folder",
      "status": "drift_detected",
      "historic": {"unique_item_count": 8921.0, "file_count": 7208.0, "folder_count": 1713.0, "file_size_gb": 39.78},
      "current":  {"unique_item_count":  401.0, "file_count":  283.0, "folder_count":  118.0, "file_size_gb":  2.73},
      "drift":    {"unique_item_count": -8520.0, "file_count": -6925.0, "folder_count": -1595.0, "file_size_gb": -37.05},
      "drift_pct": {"unique_item_count": -95.5, "file_count": -96.07, "folder_count": -93.11, "file_size_gb": -93.14},
      "tolerance_pct": 5.0,
      "generated_at": "2026-05-27T23:09:13.954822+00:00",
      "guardrails": {"external_systems": "read_only", "writeback": "none", "metadata_only": true, "compares_counts_only": true, "source_documents_copied": false}
    }
  },
  "guardrails": {"external_systems": "read_only", "metadata_only": true, "delta_token_storage": "sqlite", "no_writeback": true}
}
```

## Post-apply SQLite snapshot

| Table | Pre | Post | Delta |
|---|---|---|---|
| `construction_drive_item_inventory` | 0 | 401 | +401 |
| `construction_delta_tokens` | 0 | 0 | 0 |
| `construction_crawl_receipts` | 0 | 1 | +1 |

`401` inventory rows = `items_new` (415 distinct items seen across 2 pages, of which 15 were duplicates between pages and resolved as `items_updated`).

### `construction_crawl_receipts` row (Tropical)

```
id  | run_id                                 | mode  | status | pages | items_seen | new | upd | del | delta_link_recorded | started_at                          | finished_at
1   | f2d87cc7-5dd5-4b9e-a728-9ac928894414   | apply | ok     | 2     | 416        | 401 | 15  | 0   | 0                   | 2026-05-27T23:09:11.143076+00:00     | 2026-05-27T23:09:13.955598+00:00
```

(`delta_link_recorded` is INTEGER `0` in SQLite, projected as `false` in JSON.)

### Inventory schema (`PRAGMA table_info`)

```
source_key TEXT NOT NULL, drive_id TEXT NOT NULL, item_id TEXT NOT NULL,
name TEXT, web_url TEXT, parent_path TEXT, size_bytes INTEGER,
is_folder INTEGER NOT NULL DEFAULT 0, last_modified TEXT, etag TEXT,
status TEXT NOT NULL DEFAULT 'active',
first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
last_seen_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
```

No `body`, `content`, `text`, `excerpt`, `preview`, `full_text`, or
similar content column. `web_url` is per-item SharePoint provenance
(not a delta-continuation URL). The static schema scan that enforces
this lives at `tests/test_construction_store_repositories.py::test_no_body_or_text_columns_in_inventory`.

### Sample of 5 persisted inventory rows

```
01KUIR4CQ2PPTQQ7YHBVOI7QFDXOY5WAV4 | Div 10                                                              | is_folder=1 |   60537407 | 2024-09-03 | https://hedrickbrotherscom.sharepoint.com/sites/2023Projects/.../Div%2010
01KUIR4CQ4OO7ESUP3T5N3ISXRMGBR4A25 | Tropical World Nursery-Buyout Summary 082624.pdf                    | is_folder=0 |      91875 | 2024-08-26 | https://hedrickbrotherscom.sharepoint.com/.../Buyout%20Summary%20082624.pdf
01KUIR4CQ4OVSSLGGRCBG2CLG2WCTRSA3X | RFI PC-39 - Response and Drawing Clarification.pdf                  | is_folder=0 |    2628150 | 2024-10-14 | https://hedrickbrotherscom.sharepoint.com/.../RFI%20PC-39%20-%20Response%20and%20Drawing%20Clarification.pdf
01KUIR4CQ7FZXWY5F6CVNZ5BTURKTP7MHG | 5-Tropical World Nursery-SLF (GMP) Rev2.pdf                         | is_folder=0 |      95447 | 2024-08-15 | https://hedrickbrotherscom.sharepoint.com/.../5-Tropical%20World%20Nursery-SLF%20(GMP)%20Rev2.pdf
01KUIR4CQA6G6ESIBISBN2V7S4PECIIM65 | Boynton Beach Tropical World Comcast Managed WIFI SOW _ 073124.xlsx | is_folder=0 |    9530491 | 2025-01-15 | https://hedrickbrotherscom.sharepoint.com/.../Doc.aspx?sourcedoc=%7B49BCF100-2820-5B90-AAFE-5C79048433DD%7D
```

Each row carries item id, name, is_folder, size, last_modified, web_url.
No body, no content, no extracted text.

## Delta-link containment

The 2-page partial enumeration **did not** receive an `@odata.deltaLink`
from Microsoft Graph — Graph emits `deltaLink` only on the **last** page
of full enumeration. The earlier pages carry `@odata.nextLink`
continuation cursors which the crawler consumes internally (never
stored, never logged). `--max-pages 2` capped enumeration before the
final page, so no delta token was issued for this run.

| Check | Expected | Observed | OK |
|---|---|---|---|
| `receipt.delta_link_recorded` | `false` (no deltaLink received) | `false` | ✓ |
| `construction_delta_tokens` rows for Tropical | 0 (nothing to store) | 0 | ✓ |
| Raw `@odata.deltaLink` substring in CLI output | absent | absent (`grep -iE 'odata\.deltalink|@odata\.nextlink|skiptoken' /tmp/tropical-apply.json` → exit 1, no matches) | ✓ |
| Raw delta substring in this evidence file | absent | absent (grepped post-write before commit) | ✓ |
| Construction vault projection | unchanged (no `sync` step ran) | unchanged | ✓ |

When a future apply runs without the `--max-pages` cap (or with a cap
high enough to reach the final page, estimated ~22 pages for the full
~8921-item Tropical tree at ~400 items/page), the final `@odata.deltaLink`
URL will be issued by Graph and persisted to the
`construction_delta_tokens.delta_link` column **only**. The receipt's
`delta_link_recorded` will flip to `true`, but no raw URL will leave that
table — the only public signal remains the boolean.

## Baseline comparison (now meaningful)

| Axis | Historic (Phase 02) | Current (apply, partial) | Drift | Drift % |
|---|---|---|---|---|
| `unique_item_count` | 8921 | 401 | -8520 | -95.50% |
| `file_count` | 7208 | 283 | -6925 | -96.07% |
| `folder_count` | 1713 | 118 | -1595 | -93.11% |
| `file_size_gb` | 39.78 | 2.73 | -37.05 | -93.14% |

`status: drift_detected` — the comparator correctly flags the gap since
the partial 2-page apply enumerated only ~4.5% of the baseline universe.
Tolerance is 5%; observed drift far exceeds it, which is the **expected
and intentional** outcome of a `--max-pages 2` apply against a 22-page
tree. A future full-enumeration apply (no max-pages cap) is expected to
converge to within tolerance.

## Index status delta (Tropical)

| Field | Pre | Post |
|---|---|---|
| `resolution_status` | `graph_delta_ready` | `graph_delta_ready` |
| `inventory_counts` | `{}` | `{"active": 401}` |
| `last_sync_at` | `null` | `null` (set from `delta_tokens.last_sync_at`; no row written) |
| `last_receipt_status` | `null` | `"ok"` |
| `last_receipt_finished_at` | `null` | `"2026-05-27T23:09:13.955598+00:00"` |

`last_sync_at` correctly remains `null` because no delta token row was
persisted; once a full enumeration runs and a `delta_link` is recorded,
that field will populate.

## No-writeback / no-leak attestation

- All Microsoft Graph calls were `GET` against `/drives/{drive_id}/items/{folder_item_id}/delta`. No `POST`, `PUT`, `PATCH`, or `DELETE`.
- SQLite writes confined to three construction tables, all in the local app-support DB outside the repo: `construction_drive_item_inventory` (+401 rows), `construction_crawl_receipts` (+1 row). `construction_delta_tokens` was correctly **not** written (no delta token to store).
- No file in the Obsidian construction vault was created or modified — this prompt's apply path does not project to Markdown; that is a separate `hb-assistant construction-agent sync` operation.
- Inventory rows carry no body / content / text / excerpt / preview fields (schema enforced by repo test `test_no_body_or_text_columns_in_inventory`).
- Sample items in the CLI output carry only `id, name, is_folder, size, last_modified, deleted`.
- `web_url` is per-item SharePoint URL (item provenance, intentional metadata). It is **not** the Graph `@odata.deltaLink` continuation token — that is the only URL class the prompt forbids leaking and it was not even issued.
- The CLI output contains no literal `@odata.deltaLink`, `@odata.nextLink`, `skiptoken`, or `Bearer ` token strings.
- This evidence file contains no raw delta-link URL (verified by post-write grep).
- Guardrail blocks emitted in payload: `external_systems: read_only`, `metadata_only: true`, `delta_token_storage: sqlite`, `no_writeback: true`.

## Targeted test results

```
$ python -m pytest tests/test_construction_graph_delta.py tests/test_construction_store_repositories.py tests/test_construction_manifests.py
112 passed in 2.67s
```

(Includes `test_no_body_or_text_columns_in_inventory` and the
`test_delta_token_round_trip` lifecycle test in
`test_construction_store_repositories.py`, plus the two
`scopes_for_source_kind` tests added in commit `16df1ce`.)

## Guardrail attestation

- [x] Apply succeeded with clear, safe outcome (`status: ok`).
- [x] No Microsoft 365 mutation (GET-only delta endpoint).
- [x] No raw delta-link leak (none even issued; if issued, would be confined to `construction_delta_tokens.delta_link`).
- [x] Inventory rows are metadata-only; schema scan-tested.
- [x] Pre/post SQLite snapshot consistent with receipt counts (`inventory delta == items_new`).
- [x] Baseline comparison populated and interpretable (`status: drift_detected`).
- [x] Obsidian construction vault untouched (no `sync` step ran).
- [x] No CLI/test regressions (`112 passed`).
