# 10 — Operator runbook (source-watch)

All commands are out-of-band operator/CLI tooling. None are exposed to MCP clients. Dry-run first.

## Prerequisites
- `pip install -e ".[watch]"` for the native watchdog backend (absent → polling fallback, reported as
  `backend_available:false`, not an error).
- Configured file roots (`obsidian_mcp` `external_sources`) and, for the structure layer, matching
  `source_structure.scan_roots` keys. Mismatched keys: pass `--structure-root-map-json`.

## Initial bootstrap (idempotent, safe to re-run)
```bash
# 1. Plan (writes nothing)
hb-assistant source-watch bootstrap --all-roots --dry-run

# 2. Apply both layers
hb-assistant source-watch bootstrap --all-roots

# 3. Verify readiness (path-safe projection)
hb-assistant source-watch status
```
Partial builds: `--file-index-only` or `--structure-only`. `--root-key K` for one root.
A root is `watcher_ready` only when BOTH layers are bootstrapped.

## Watcher gating / start
```bash
hb-assistant source-watch run                     # gate only: reports per-root run_state; exit 2 if any unbootstrapped
hb-assistant source-watch run --bootstrap-if-needed
hb-assistant source-watch run --start             # explicit: launch the real (blocking) watcher — AUTHORIZED enablement only
```
Run-state per root: `disabled_by_config` | `not_bootstrapped` | `backend_unavailable` | `running`.

## Scheduled maintenance (suggested cadence — not hardcoded)
```bash
# frequent: drain the file-index queue
hb-assistant source-watch drain --max-items 500 --max-seconds 300
# hourly-ish: catch missed events + flag folder drift
hb-assistant source-watch reconcile --all-roots --scan-type lightweight
# nightly: full reconcile + structure re-bootstrap when drift flagged
hb-assistant source-watch reconcile --all-roots --scan-type full
hb-assistant source-watch bootstrap --all-roots --structure-only   # when health shows directory_change_detected
```

## Reading health (client + operator)
`assistant_source_index_health` now returns `bootstrap`, `watcher`, `file_index`, `structure_index`
(incl. `directory_change_detected` / `structure_refresh_recommended` / `dirty_bridge_enabled:false`),
`reconciliation`, `recommended_operator_action`, `safe_for_client_answering`. Directory-architecture
drift is *flagged* here — this branch does NOT auto-rebuild structure (bridge deferred); act on the
recommendation.

## Rollback
Additive-only. V117 tables are inert until the CLI runs; new CLI group + health sections are
backward-compatible (tool count unchanged 87/14). Revert = drop the branch/worktree; this branch touches
no live DB. Recovery anchors (pre-v116 DB backup, prior images) remain untouched.
