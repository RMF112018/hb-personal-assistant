# 09 — Delta Sync Readiness Proof (Phase 06A)

**Prompt:** Prompt 08 — Delta Sync Hardening · **Date:** 2026-05-30
**Posture:** Read-only; dry-run default; no new migration; no scope change; permission tightening deferred; metadata only.

## Hardened flow

1. **Follow `@odata.nextLink` until exhausted**, then capture the final `@odata.deltaLink` (rolling).
2. **Persist deltaLink in SQLite only** (`construction_source_sync_state.delta_link`); everywhere else only the `sha256:<12>` fingerprint is rendered.
3. **Deleted facet** → counted as `items_deleted` and upserted as `deleted=True` into `construction_drive_items` (apply).
4. **Stale token / `410 Gone` → `requires_rebaseline`** (token cleared, status recorded; never silently discarded).
5. **Canonical source sync state updated** (`upsert_source_sync_state`): delta_link (SQLite), fingerprint, last_successful/attempted, last_change_count, sync_status; plus a `construction_source_crawl_runs` row + a `delta_sync` processing receipt.

Reuses the P06 `normalize_drive_item` + `upsert_drive_item`; the V2 `ConstructionDeltaCrawler` is left unchanged (parallel path).

## Mocked dry-run — initial delta (deltaLink captured, deleted handled)

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

## Mocked — stale token / 410 → requires_rebaseline

```json
{
  "run_id": "351e912c-8212-4e20-8917-83eafa9aaecb",
  "source_id": "sp_2023projects_23_435_01_tropical_sl",
  "kind": "sharepoint_project_drive_folder",
  "scope": "sharepoint_project_drive_folder",
  "mode": "dry_run",
  "endpoint": "/drives/b!tropical-drive/items/01TROPICALFOLDER/delta",
  "started_from": "initial",
  "status": "requires_rebaseline",
  "pages_seen": 0,
  "items_seen": 0,
  "items_changed": 0,
  "items_deleted": 0,
  "items_persisted": 0,
  "delta_link_fingerprint": null,
  "delta_link_recorded": false,
  "truncated_by": "none",
  "note": "stale delta token; cleared \u2014 next run re-baselines",
  "error_redacted": "graph_410_stale_delta_token"
}
```

## Guardrails

- `delta_token_storage: sqlite_only` · `delta_link_rendered: fingerprint_only`
- No raw delta/next link, token, signed URL, downloadUrl, or full content in any report/evidence/log.
- Live `graph files delta` degrades to `auth_required` (token expired at capture).

## Stop-condition check

No M365 writeback, no permission tightening, no source-file copy into Obsidian, no full text persisted,
**no raw delta links exposed** (fingerprint only), no review-routing bypass.
