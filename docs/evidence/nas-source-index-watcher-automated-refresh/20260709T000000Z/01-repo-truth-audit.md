# 01 — Repo-truth audit (before implementation)

Base: `origin/main` @ `9dcebac3` (PR #288 merged — source-index client-performance hardening present:
`assistant_source_index_health`, `assistant_source_query_plan`, structure tools, `assistant_output_*`).
Precondition satisfied; branched from a clean worktree off `origin/main`.

## What already exists (REUSED, not rebuilt)

| Concern | Location | Notes |
|---|---|---|
| Content-index engine | `obsidian_mcp/source_indexer.py` | `scan_source_root` (walk+index+**delete-reconcile**, mtime+sha256 skip), `drain_queue`, `request_rebuild`, unsupported/skip codes |
| Durable file-event queue + k/v state | `source_intelligence_events`, `source_intelligence_state`; `obsidian_mcp/source_index_repository.py` | `enqueue_event`, `claim_queued`, `requeue_stuck`, `queue_health`, watcher lease/heartbeat |
| Watcher daemon | `obsidian_mcp/source_watch.py` `SourceWatcher` | watchdog **or** polling fallback, 900s lease, heartbeat; watchdog is optional dep `.[watch]` |
| Freshness / health | `obsidian_mcp/source_health_service.py`, `nas_mcp/freshness.py` | `source_index_health` (path-safe aggregation) |
| Structure layer V115/V116 | `cli/source_structure.py`, `obsidian_mcp/source_structure_*`, `source_structure_runs` | idempotent, root-scoped `scan-roots`; **no atomic replace, no subtree mode** |
| Source-root config | `obsidian_mcp/config.py` `ExternalSourceRoot`; `config/models.py` `SourceStructureConfig.scan_roots` | **two key spaces** — file `source_root_key` vs structure `scan_roots` dict |
| Path redaction | `source_health_service.py`, `source_structure_service.py`, `nas_mcp/path_safe.py`, `redaction.py` | health emits only `root_key`/counts |

## Gaps this branch closes

1. No CLI to build the content index on the NAS (only MCP `rebuild_source_index`, **blocked** on NAS MCP).
2. No bootstrap coordination across both layers with durable per-root readiness + watcher-ready gating.
3. No safety-net reconciliation command.
4. Health did not report bootstrap/watcher/queue/reconciliation/drift; `SourceWatcher.status()` leaks
   absolute `cwd`/`db_path` (so health reads durable k/v + heartbeat only, never that blob).

## Decisions forced by repo-truth
- **Reuse** `source_intelligence_events` (file queue), `source_intelligence_state` (watcher k/v), and
  `source_structure_runs` — do NOT build the prompt's parallel 8-table schema.
- Schema head is **116** (`LATEST_SCHEMA_VERSION`); add additive **V117** (2 tables).
- Structure bootstrap calls the service/repository **in-process** (no CLI subprocess recursion).
- Reconciliation reuses the existing `reindex_requested` / `deleted` event vocabulary.
