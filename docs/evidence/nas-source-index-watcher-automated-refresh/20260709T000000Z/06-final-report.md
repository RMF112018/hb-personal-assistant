# 06 — Final report: NAS source-index bootstrap + watcher-readiness (core slice)

| Field | Value |
|---|---|
| Branch | `ops/source-index-watcher-automated-refresh-20260709` |
| Base commit | `9dcebac3` (`origin/main`, PR #288 merged) |
| Worktree | `/Users/bobbyfetting/hb-personal-assistant-worktrees/ops/source-index-watcher-automated-refresh-20260709` |
| Final HEAD | **uncommitted** — changes staged in worktree, awaiting explicit commit authorization |
| Schema migration | **V117** (`LATEST_SCHEMA_VERSION` 116 → 117) |

## Tables added (2, additive)
- `source_index_bootstrap_state` — per-root file/structure bootstrap flags + `watcher_ready` gate.
- `source_index_reconciliation_runs` — lightweight/full reconciliation receipts.
Reused (no duplication): `source_intelligence_events`, `source_intelligence_state`, `source_structure_runs`.
Dropped from prompt: `source_index_bootstrap_runs`, plus 4 parallel watch/queue tables and
`source_structure_dirty_scopes` (deferred with the bridge).

## CLI added — `hb-assistant source-watch`
`bootstrap` (--all-roots/--root-key/--file-index-only/--structure-only/--dry-run/--force/
--structure-root-map-json), `run` (--require-bootstrap/--bootstrap-if-needed/--start), `status`,
`drain` (--max-items/--max-seconds), `reconcile` (--scan-type lightweight|full).

## MCP surface
No new tool. `assistant_source_index_health` extended with `bootstrap`, `watcher`, `file_index`,
`structure_index` (incl. `directory_change_detected`/`structure_refresh_recommended`/
`dirty_bridge_enabled:false`), `reconciliation`, `recommended_operator_action`,
`safe_for_client_answering`. **Tool count unchanged: 87 / 14 groups** (`05-tool-inventory.txt`).

## Files
New: `store/source_index_bootstrap_tables.py`, `store/source_index_bootstrap_repository.py`,
`obsidian_mcp/source_bootstrap.py`, `cli/source_watch.py`,
`tests/test_source_index_watcher_automated_refresh.py`, `tests/test_migrator_v117_source_index_bootstrap.py`.
Modified: `store/migrator.py`, `cli/main.py`, `obsidian_mcp/source_health_service.py`,
`tests/test_schema_version_head_consistency.py`.

## Behavior
- **File bootstrap**: `scan_source_root` per root (walk + index + delete-reconcile, mtime+sha256 skip);
  dry-run = stat-only count, zero writes. Idempotent (2nd run: 0 re-indexed, 2 skipped).
- **Structure bootstrap**: in-process `scan_roots`→`classify_tree`→`persist_records` (no subprocess).
- **Watcher readiness**: `watcher_ready = file_bootstrapped AND structure_bootstrapped`; partial reported
  honestly; watcher refuses unbootstrapped roots by default.
- **Backend**: reuses existing `SourceWatcher` (watchdog **or** polling fallback). Polling reported as
  `backend_available:false`, not an error.
- **File queue drain** updates `source_intelligence_*` incrementally; deleted files stop being active
  search hits (validation step 14).
- **Structure updates**: scoped subtree mutation NOT available in V115 → reconciliation *flags* drift
  (set-based folder comparison), operator re-bootstraps structure. Auto-bridge deferred.
- **Debounce**: reuses the existing watcher/queue debounce; no new debounce layer this branch.
- **Reconciliation**: lightweight (stat-compare + enqueue) and full (`scan_source_root`); both record a run.

## Validation
- Baseline focused suite: **green** (`00-baseline-pytest-output.txt`).
- Final focused suite: **131 passed** (`04-final-pytest-output.txt`); new suite **36 passed** (~32s after
  DB-template optimization); representative migrator canary (V93/V94/V115) green.
- Local validation matrix: **16/16** (`03-local-validation-matrix.{md,json}`).
- Health output path-safe (no absolute/home paths) — validation step 9 + dedicated tests.

## Safety posture
Bootstrap/rebuild/drain are CLI/operator-only; never in `ASSISTANT_*` groups or `GATEWAY_ALLOWLIST`.
Health reads durable k/v + heartbeat only (never `SourceWatcher.status()`'s `cwd`/`db_path`). Additive
schema; backward-compatible. No live DB touched; no push/PR/deploy.

## Deferred
`source_structure_dirty_scopes` + automatic directory-event→structure-rebuild bridge; new MCP
queue-status tool; true structure subtree mutation; production service/launchd enablement.

## Operational steps to enable on NAS
See `10-operator-runbook.md`: `bootstrap --all-roots` → `status` → (authorized) `run --start` → scheduled
`drain` + `reconcile`; re-`bootstrap --structure-only` when health flags `directory_change_detected`.

## Rollback
Additive-only; V117 tables inert until CLI runs. Revert = drop branch/worktree. Recovery anchors
(pre-v116 DB backup, prior images) untouched.

## Recommended next phase
Follow-up branch: structure-dirty bridge (`source_structure_dirty_scopes` V118 + directory-event markers
+ dirty worker with full-root fallback), then supervised NAS bootstrap dry-run→apply→health→watcher
enablement→24h observation.
