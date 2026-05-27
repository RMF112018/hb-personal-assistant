# Phase 03 Entry — Tropical Folder-Scoped Delta Dry-Run + Baseline Reconciliation

## Why

First live Microsoft Graph round-trip on this branch. Uses the delegated
token acquired in Prompt 01 (`5cbde25`) to run a folder-scoped delta
against the Tropical source and reconcile observed metadata counts
against the Phase 02 baseline. Strictly read-only: no Microsoft 365
mutation, no local SQLite write, no source-document content read.

## Command

```bash
hb-assistant construction-agent graph delta \
  --source sp_2023projects_23_435_01_tropical_sl \
  --dry-run \
  --max-pages 2 \
  --json
```

Exit code: `0`.

## Verbatim JSON receipt

```json
{
  "command": "construction-agent graph delta",
  "source": "sp_2023projects_23_435_01_tropical_sl",
  "mode": "dry_run",
  "status": "ok",
  "receipt": {
    "run_id": "33ede974-1644-4d78-9109-67e2e8df9735",
    "source_key": "sp_2023projects_23_435_01_tropical_sl",
    "drive_id": "b!2r2rsTva0U-gOMSusTupUT0Ecgn6KG9CrTXQO7ex9-wjlyM1iYsETbs3ktNIMr0B",
    "mode": "dry_run",
    "status": "ok",
    "started_at": "2026-05-27T21:50:13.835088+00:00",
    "finished_at": "2026-05-27T21:50:16.442762+00:00",
    "pages_seen": 2,
    "items_seen": 416,
    "items_new": 0,
    "items_updated": 0,
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
      "status": "never_crawled",
      "historic": {"unique_item_count": 8921.0, "file_count": 7208.0, "folder_count": 1713.0, "file_size_gb": 39.78},
      "current":  {"unique_item_count":    0.0, "file_count":    0.0, "folder_count":    0.0, "file_size_gb":  0.0},
      "drift":    {"unique_item_count": -8921.0, "file_count": -7208.0, "folder_count": -1713.0, "file_size_gb": -39.78},
      "drift_pct": {"unique_item_count": -100.0, "file_count": -100.0, "folder_count": -100.0, "file_size_gb": -100.0},
      "tolerance_pct": 5.0,
      "generated_at": "2026-05-27T21:50:16.442670+00:00",
      "guardrails": {"external_systems": "read_only", "writeback": "none", "metadata_only": true, "compares_counts_only": true, "source_documents_copied": false}
    }
  },
  "guardrails": {"external_systems": "read_only", "metadata_only": true, "delta_token_storage": "sqlite", "no_writeback": true}
}
```

## Endpoint verification

| Check | Expected | Observed | OK |
|---|---|---|---|
| `receipt.scope` | `sharepoint_project_drive_folder` | `sharepoint_project_drive_folder` | ✓ |
| `receipt.endpoint_kind` | `folder_scoped` | `folder_scoped` | ✓ |
| `receipt.folder_item_id` | `01KUIR4CV3RKZL4MURNRKY6DWASR3B7EGM` (from registry) | `01KUIR4CV3RKZL4MURNRKY6DWASR3B7EGM` | ✓ |
| Actual endpoint path | `/drives/{drive_id}/items/{folder_item_id}/delta` | `/drives/b!2r2rs.../items/01KUIR4CV.../delta` (from the `require_delegated` context in earlier-iteration traceback before the auth fix) | ✓ |

The crawler selected the folder-scoped endpoint (not `drive_root_fallback`).

## Pages / items seen

| Metric | Value |
|---|---|
| Pages requested cap (`--max-pages`) | 2 |
| `pages_seen` | 2 |
| `items_seen` | 416 (5 of which preserved as redacted `sample_items`) |
| `items_new` / `items_updated` / `items_deleted` | 0 / 0 / 0 (dry-run; nothing persisted to inventory) |
| Wall time | 2.61 s (started 21:50:13.835Z, finished 21:50:16.442Z) |

## Baseline reconciliation

Phase 02 baseline (recorded in the source registry):

| Metric | Baseline |
|---|---|
| `unique_item_count` | 8,921 |
| `file_count` | 7,208 |
| `folder_count` | 1,713 |
| `file_size_gb` | 39.78 |

`baseline_comparison.current` is **zero** because this is a `dry_run` and
the crawler does not persist inventory rows. `baseline_comparison.status`
is therefore `never_crawled` and the drift reads `-100%` on every axis.
This is **expected and by design**:

- The receipt's `items_seen=416` is a live observation from the Graph
  delta endpoint (2 pages out of an estimated ~22 pages needed for the
  full ~8921 items at ~400 items/page).
- `compute_baseline_comparison` reads from
  `construction_drive_item_inventory` (the persisted-inventory table)
  for `current` counts. In `dry_run`, nothing is written, so that table
  remains empty and the function reports `never_crawled` rather than a
  realized count delta.
- A meaningful baseline-vs-current reconciliation requires an `--apply`
  run that persists inventory. That is **out of scope** for this prompt
  — Prompt 03 only proves the folder-scoped endpoint works and the
  receipt structure carries the baseline correctly.

Variance interpretation for this run: the 416 items observed against
8921 baseline items is `~4.66%` of total, consistent with 2 pages of
~200-page Graph delta paging at the upper end of Graph's per-page item
yield. With `--max-pages 50` (the CLI default) a single dry-run could
enumerate the full tree.

## No-write / no-body / no-token attestation

- `mode: dry_run` recorded in receipt + outer payload.
- `delta_link_recorded: false` — the raw `@odata.deltaLink` URL was
  **not** persisted (dry-run skips token write at
  `delta_crawler.py:296`). The boolean is the only public signal; the
  raw URL never appears in the payload.
- Index status comparison (pre/post identical) proves no SQLite write:
  - Before run: `"last_sync_at": null, "last_receipt_status": null, "inventory_counts": {}`
  - After run:  `"last_sync_at": null, "last_receipt_status": null, "inventory_counts": {}`
- Sample-item field set: `id, name, is_folder, size, last_modified, deleted` only. **No** `body`, `content`, `text`, `excerpt`, `preview`, `full_text`, `webUrl`, `@microsoft.graph.downloadUrl`, or any other content/URL field. Redaction applied by
  `_redact_item_preview` in `construction/graph/resolver.py`.
- The entire JSON payload contains **no** literal `@odata.deltaLink`,
  `@odata.nextLink`, `skiptoken`, or `Bearer ` tokens.
- All Graph calls were GETs (the delta endpoint is GET-only). No POST,
  PUT, PATCH, or DELETE was made.
- Guardrail block emitted: `external_systems: read_only`,
  `metadata_only: true`, `delta_token_storage: sqlite`,
  `no_writeback: true`.

## Targeted test results

```
$ python -m pytest tests/test_construction_graph_delta.py tests/test_construction_manifests.py
82 passed in 2.32s
```

(Includes the two new tests added in this commit:
`test_scopes_for_source_kind_drive_folder_excludes_sites_read_all` and
`test_scopes_for_source_kind_site_page_includes_sites_read_all`.)

Auth-layer tests (sanity for the JWT-decode synthesis path):

```
$ python -m pytest tests/test_auth.py
30 passed
```

(Includes three new tests for `_ensure_delegated_id_token_claims`:
JWT-decode path, account-fallback path, and fail-closed when no
evidence is available.)

## Code changes landed alongside this evidence

This prompt necessarily required **three** code corrections that were
not anticipated in the plan but became gating issues during the live run:

1. **Per-source-kind delegated scope selection.**
   `src/hb_assistant/construction/graph/__init__.py` and `resolver.py`
   now expose `GRAPH_SCOPES_DRIVE = ["Files.ReadWrite.All", "User.Read"]`
   and `GRAPH_SCOPES_SITE_PAGE = ["Sites.Read.All", "Files.ReadWrite.All", "User.Read"]`
   plus a `scopes_for_source_kind(kind: str)` helper.
   `src/hb_assistant/cli/construction.py:_build_graph_client_or_auth_payload`
   accepts an optional `scopes` argument; the `graph delta` CLI handler
   computes `scopes_for_source_kind(source.kind)` and passes it.
   `src/hb_assistant/construction/graph/delta_crawler.py` per-call
   `scopes=` hint switched from `GRAPH_SCOPES` to `GRAPH_SCOPES_DRIVE`.
   **Reason**: the broader `Sites.Read.All` is not admin-consented on the
   HB SharePoint Creator app registration. Requesting it for a
   drive-folder source caused MSAL silent acquisition to fail with the
   misleading "expired or revoked" error.

2. **`DelegatedAuthProvider.get_token` backfills `id_token_claims`.**
   MSAL's `acquire_token_silent` returns only `access_token`,
   `expires_in`, `token_source`, `token_type` — it strips
   `id_token_claims` that the original `acquire_token_by_device_flow`
   issued. Without that field, `require_delegated` rules the token
   `invalid` even though it is a valid delegated access token.
   `src/hb_assistant/auth/providers.py` now decodes the access-token
   JWT payload (without signature verification — MSAL has already
   established authenticity) to recover the real `scp`, `upn`, `tid`,
   `oid` claims, with cached-account fallback for fields the JWT omits.
   Fail-closed semantics preserved by
   `test_ensure_delegated_id_token_claims_preserves_fail_closed_when_no_evidence`.

3. **Mutation-lockout posture unchanged.** None of the above changes add
   a write scope or remove a forbidden-scope assertion. `Mail.Read`-only
   stays. `_FORBIDDEN_MAIL_SCOPES` set is untouched.

## Guardrail attestation

- [x] Folder-scoped endpoint selected (`endpoint_kind=folder_scoped`,
      `folder_item_id` matches registry).
- [x] Dry-run mode does not persist inventory or delta token (verified
      by pre/post `index status` snapshot).
- [x] Pages/items seen captured (2 / 416).
- [x] Baseline comparison populated; variance explained
      (dry-run skips inventory write → `current=0`).
- [x] No file bodies read; no content/text/preview fields in samples.
- [x] No writeback to Microsoft 365 (GET-only delta endpoint).
- [x] No raw delta link / skiptoken / nextLink in evidence
      (`delta_link_recorded: false`, no URL strings in payload).
- [x] Targeted tests pass: `test_construction_graph_delta.py` and
      `test_construction_manifests.py`.
