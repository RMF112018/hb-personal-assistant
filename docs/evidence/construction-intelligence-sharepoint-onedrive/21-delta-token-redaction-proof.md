# 21 — Delta Token Redaction Proof (Phase 06A)

**Prompt:** Prompt 08 — Delta Sync Hardening · **Date:** 2026-05-30

## Invariant

The raw Microsoft Graph `@odata.deltaLink` / `@odata.nextLink` (token-bearing) is **persisted to SQLite
only** (`construction_source_sync_state.delta_link`) and is **never** rendered in any report, CLI JSON,
evidence file, or log. Everywhere else only `delta_link_fingerprint` (`sha256:<first-12-hex>`,
non-reversible) appears. The incremental start path (a stored prior deltaLink) is used as the request
path but is never echoed; the report `endpoint` is the LOGICAL delta template, not the raw URL.

## Captured report (the Graph response carried a raw `...token=<delta-token>`)

```json
{
  "run_id": "8a79014a-da9a-47e1-a63b-57cfb71bdf06",
  "source_id": "sp_2023projects_23_435_01_tropical_sl",
  "kind": "sharepoint_project_drive_folder",
  "scope": "sharepoint_project_drive_folder",
  "mode": "dry_run",
  "endpoint": "/drives/b!tropical-drive/items/01TROPICALFOLDER/delta",
  "started_from": "initial",
  "status": "ok",
  "pages_seen": 1,
  "items_seen": 2,
  "items_changed": 1,
  "items_deleted": 1,
  "items_persisted": 0,
  "delta_link_fingerprint": "sha256:b31a345247ca",
  "delta_link_recorded": false,
  "truncated_by": "none",
  "note": null,
  "error_redacted": null
}
```

- `delta_link_fingerprint` = `sha256:b31a345247ca` (only this is rendered).
- `endpoint` = `/drives/b!tropical-drive/items/01TROPICALFOLDER/delta` (logical template; no token).
- No token-shaped substring of the raw deltaLink appears anywhere in the report.

## Storage boundary (enforced in code + tests)

| Location | Raw deltaLink? | Rendered as |
| --- | --- | --- |
| `construction_source_sync_state.delta_link` (SQLite) | yes (apply only) | — |
| Report / CLI `--json` / evidence / logs | **never** | `delta_link_fingerprint` (`sha256:<12>`) |

Proven by `tests/test_graph_files_delta_sync.py`:
`test_initial_delta_captures_deltalink_and_redacts`, `test_apply_persists_state_items_and_receipt`
(raw token only in the SQLite `delta_link` column; absent from the report + receipt detail),
`test_cli_delta_runs_and_redacts` (no raw token in CLI output).
