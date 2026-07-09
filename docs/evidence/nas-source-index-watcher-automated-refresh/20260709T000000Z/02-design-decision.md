# 02 — Design decision

## Scope (operator-approved core slice, with amendments)
IN: file + structure bootstrap, per-root readiness state, `source-watch` CLI (bootstrap/run/status/
drain/reconcile), watcher-readiness gating, health extension, lightweight+full reconciliation.
DEFERRED: `source_structure_dirty_scopes` table + automatic directory-event→structure-rebuild bridge;
new `assistant_*` MCP tool (tool count stays **87/14**); live structure auto-refresh; production service
enablement.

## Schema — additive V117 (2 tables), reuse the rest
- `source_index_bootstrap_state` — per file-index `source_root_key`: file/structure bootstrapped flags,
  last bootstrap/success timestamps + status, `watcher_ready`, last_error. **No absolute paths.**
- `source_index_reconciliation_runs` — lightweight/full scan receipts (counts + timestamps + status).
- **Dropped** `source_index_bootstrap_runs`: per-root readiness is in `bootstrap_state`; file activity in
  `source_intelligence_events/_state`; structure activity in `source_structure_runs`; coordinated
  run-level receipt is the evidence JSON.
- **Reused**: `source_intelligence_events` (file queue), `source_intelligence_state` (watcher
  lease/heartbeat + the structure-drift signal k/v), `source_structure_runs` (structure runs).

## Answers to the amendments
1. **Drift surfaced despite deferred bridge** — reconciliation compares the indexed folder set to a fresh
   bounded structure scan (same scanner pruning both sides → real added/removed architecture, not a
   count artifact) and writes a `structure_drift:<root>` k/v signal. Health exposes
   `directory_change_detected`, `structure_refresh_recommended`, `dirty_bridge_enabled:false`, and a
   concrete `recommended_operator_action`.
2. **Explicit root-key mapping** — `resolve_structure_key` = explicit operator map → exact match → None.
   No fuzzy/substring matching. Unmapped file roots report structure `not_configured`. Tested 4 ways.
3. **Structure bootstrap in-process** — `scan_roots`→`classify_tree`→`persist_records` called directly;
   no `hb-assistant source-structure` subprocess.
4. **Event-vocabulary reuse** — reconciliation enqueues existing `reindex_requested` / `deleted` events;
   no new event types.
5. **Run-state enum** — `disabled_by_config` / `not_bootstrapped` / `backend_unavailable` / `running`,
   authoritative in `source-watch run`/`status`, projected into health per root.

## Readiness rule (conservative)
`watcher_ready = file_index_bootstrapped AND structure_index_bootstrapped`. File-only or structure-only
is partial → not ready, reported honestly. Watcher refuses unbootstrapped roots by default.

## Safety posture
Bootstrap/rebuild/drain stay CLI/operator-only (never `ASSISTANT_*`/`GATEWAY_ALLOWLIST`). Health reads
durable state (never `SourceWatcher.status()` which leaks `cwd`/`db_path`). Dry-run is the default plan
posture; `run` never launches a persistent watcher without explicit `--start`.
