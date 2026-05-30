# 03 — SharePoint Site & Drive Discovery Proof

**Prompt:** Prompt 04 — SharePoint Site and Drive Discovery
**Phase:** HB Construction Intelligence Phase 06 — SharePoint / OneDrive File Intelligence
**Date:** 2026-05-30
**Posture:** Production-grade site resolution + drive enumeration/matching, **metadata-only, no
content crawl**. Read-only against M365; dry-run default; **no new migration; no scope change;
permission tightening deferred.**

---

## 1. Reconciliation — reuse vs. new

- **Reused:** `ConstructionGraphResolver` (`construction/graph/resolver.py`) for site resolution by
  URL + pre-seeded ID and for ProjectHome `sharepoint_site_page` linked-source candidates
  (`deep_index_allowed: Literal[False]`).
- **New:** `construction/graph/site_drive_discovery.py` (`SiteDriveDiscovery`) adds drive
  **enumeration + matching** of a configured source against `/sites/{id}/drives`, plus the operator
  commands `graph files sites`, `graph files site resolve`, `graph files drives`.
- **Receipts:** reuse the generic `construction_processing_receipts` table via
  `insert_processing_receipt(operation="site_discovery"|"drive_discovery", detail=…)` — **no V15
  migration**. The package's proposed typed `construction_graph_*_discovery` tables are deferred.
- **Guard:** the new service asserts `assert_files_request_allowed("GET", "/sites/{id}/drives")`
  before each enumeration GET. The resolver's colon-addressed site-by-URL read
  (`/sites/{host}:/{path}`) stays on the plain client; full HTTP-guard interception + the colon-path
  matcher enhancement are deferred to the controlled-download client (Prompt 11).

## 2. Site resolution

| Source | Mode | Result |
| --- | --- | --- |
| `sp_2023projects_23_435_01_tropical_sl` (pre-seeded site_id+drive_id+folder_item_id) | dry-run | `pre_resolved`, **zero HTTP calls** (test `test_discover_site_pre_resolved_makes_no_http_call`) |
| `sharepoint_site` with `site_url` only | dry-run | `resolved` via `GET /sites/{host}:/{path}` + `GET /sites/{id}/drive`; site_id + hostname + server-relative-path populated |
| OneDrive kinds | — | `unsupported` (not a SharePoint site) |

### Live degradation (graceful, no token)

`hb-assistant graph files site resolve --source sp_2023projects_23_435_01_tropical_sl --json` at
capture time returned a structured `auth_required` envelope (cached delegated token expired):

```json
{
  "command": "graph files site resolve",
  "source": "sp_2023projects_23_435_01_tropical_sl",
  "mode": "dry_run",
  "status": "auth_required",
  "scopes": ["Sites.Read.All", "Files.ReadWrite.All", "User.Read"],
  "detail": "Failed to acquire delegated token (expired or revoked). Re-login required.",
  "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token."
}
```

No interactive login is triggered; non-interactive callers get a clean structured result. (Drive
discovery behavior is captured deterministically in `04-drive-discovery-proof.json`.)

## 3. Drive enumeration + matching

`discover_drives` resolves `site_id` (via the resolver), guard-asserts and reads
`GET /sites/{site_id}/drives` (metadata `$select=id,name,webUrl,driveType`; **never** `/items` or
`/content`), then matches the configured source by precedence:

| Precedence | Method | Confidence | Test |
| --- | --- | --- | --- |
| 1 | `drive_id` exact | high | `test_discover_drives_matches_by_drive_id`, `test_match_by_list_id` (drive_id wins when present) |
| 2 | `list_id` | high | `test_match_by_list_id` |
| 3 | `library_name` == drive.name (casefold) | medium | `test_match_by_library_name` |
| 4 | `webUrl` prefix | medium | `test_match_by_web_url_prefix` |
| — | no signal | none → `unmatched` | `test_match_none_when_no_signal`, `test_discover_drives_unmatched_when_no_signal` |

**No silent default-drive fallback:** when nothing matches, the result is `unmatched` (the discovery
default gates default-drive fallback on an explicit operator flag, not auto-applied). See
`04-drive-discovery-proof.json` for the matched-by-drive_id artifact.

## 4. ProjectHome linked-source candidates (metadata-only)

For `sharepoint_site_page` sources, `discover_drives` returns the resolver's
`linked_sources_discovered` — every site drive surfaced as a candidate with
`deep_index_allowed: false` and no content read (`test_discover_drives_site_page_returns_linked_candidates`).

## 5. Discovery receipts (dry-run vs apply)

- Dry-run persists **no** receipt (`test_dry_run_persists_no_receipt`).
- `--apply` writes one `construction_processing_receipts` row with
  `operation="site_discovery"`/`"drive_discovery"` and a redacted `detail_json`
  (`test_apply_persists_drive_discovery_receipt`); the receipt blob contains no `Bearer`/`access_token`.

## 6. Read-only guard on the enumeration path

`assert_files_request_allowed("GET", "/sites/{id}/drives")` is permitted; `POST` on the same path
raises `FileMutationBlockedError` (`test_enumeration_path_is_guard_allowlisted`).

## 7. Validation recorded

- `ruff check .` PASS (`ruff format` applied; imports fixed); `mypy src` PASS (131 files);
  `compileall` PASS.
- `pytest tests/test_graph_files_site_drive_discovery.py tests/test_construction_graph_resolver.py
  tests/test_mutation_lockout.py tests/test_graph_files_endpoint_guard.py` → all green.
- Full default-safe suite: only the pre-existing 12 email-track failures; no new failures.

## 8. Stop-Condition Check

No stop condition triggered. No M365 writeback, no permission tightening, no source-file copy into
Obsidian, no full source text persisted, no raw delta links/signed URLs/`downloadUrl`, and
review-routing is preserved (linked candidates are metadata-only with `deep_index_allowed=false`;
unmatched drives are not auto-bound). Discovery is metadata-only with **no content crawl**.
