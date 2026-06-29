# Evidence — A1.10 Source Watch Reliability, Self-Indexing Guard, Deferred-Source Maintenance

**Date:** 2026-06-29
**Branch:** `fix/source-watch-reliability-maintenance-20260629T202837Z`
**Base commit:** `f8f1bf32` (origin/main — A1.9 merged)

## Defects fixed

**1 + 2 — watcher honors fresh config; status consistent** (`source_watch.py`, `api.py`)
`SourceWatcher.start()`/`status()` take an optional `config=` (default = injected snapshot, so unit
tests are unchanged). The API layer passes the current on-disk config (`_fresh_obsidian_config()`):
`start` → `start(config=fresh)`, both status surfaces → `status(config=fresh)`. So a just-PATCHed
`external_source_watch_enabled` takes effect on `/source-watch/start` (no `/restart`), and top-level
+ nested `watch_enabled` always agree.

**3 — generated cards no longer self-index** (`source_indexer.py`, `source_watch.py`)
New `is_source_notes_path(rel_path, config)` (prefix match on `source_notes_folder`). Applied in
`scan_vault_notes` (skip) and the vault watcher `_Handler._enqueue` (vault-scoped, never enqueues a
`Source Notes/...` change). Polling is covered by the scan guard.

**4 — safe maintenance op** (`source_maintenance.py`, `source_index_repository.py`, `service.py`, `api.py`)
`retire_source_cards(repo, config, *, apply=False, delete_files=False)` retires generated cards whose
SOURCE path now matches the exclusion or deferred policy. Dry-run (default) mutates nothing and
returns counts + sample paths; `apply` marks matched generated-note rows `stale` (the existing legal
status — no new enum); `delete_files` (only with apply) removes just the card `.md` via the writer's
`resolve_markdown_write_path`. **Never** deletes source rows/files. New repo `list_generated_notes` +
`set_generated_note_status`. Operator-gated `POST /api/settings/obsidian-mcp/source-cards/retire`.

**5 — first-class deferred policy** (`config.py`, `source_indexer.py`, `source_notes.py`, `source_search.py`, `api.py`)
`source_index_deferred_path_parts` (default `["HB INSURANCE RENEWALS"]`) + `is_deferred_source_path`
(segment match, distinct from exclusions). Deferred = indexed/searchable but auto-card/summary
skipped: `_auto_generate` early-returns; the drain single-file branch indexes then marks the event
`skipped`/`deferred_path` (clean receipt, not error); `summarize_source` returns `reason=deferred_path`.
Manual `generate_source_card` is NOT blocked (operator override) — the crisp deferred↔excluded
distinction. Surfaced as `deferred_policy` in `source-index/status`. Editable UI control added.

## Files changed
- `src/hb_assistant/obsidian_mcp/`: `source_watch.py`, `source_indexer.py`, `source_notes.py`,
  `source_search.py`, `source_index_repository.py`, `config.py`, `service.py`, `source_maintenance.py` (new)
- `src/hb_assistant/construction/analytics/api.py` (fresh-config plumbing, deferred field, retire endpoint)
- `frontend/src/lib/api.ts`, `frontend/.../ObsidianMcpPanel.tsx` (+ `.test.tsx`)
- `tests/`: `test_obsidian_source_watch_reliability.py`, `test_obsidian_source_self_index_guard.py`,
  `test_obsidian_source_deferred.py`, `test_obsidian_source_maintenance.py` (new); `test_obsidian_mcp_backend.py` (extended)

## Schema / migration
**None.** Additive config field; `stale` reused for retire; `skipped` event status already existed.

## Tests (backend-tests.txt / frontend-tests.txt)
- New backend suites + endpoint additions: 33 passed focused. Full `-k "source_watch or source_index
  or obsidian or deferred or maintenance or self_index"`: **545 passed, 0 failed**.
- Frontend: typecheck clean; `ObsidianMcpPanel` **20/20** (18 prior + 2 deferred-control).
- `py_compile` all src OK; ruff clean on changed files (`service.py` I001 is pre-existing on main).

## Manual validation (live backend; watcher returned to OFF; backlog NOT drained)
- Baseline (`manual-status-before.json`): queue 0/0, watch off; `deferred_policy` =
  `["HB INSURANCE RENEWALS"]` surfaced.
- **A** (`manual-start-response.json`): PATCH watch=true → `/source-watch/start` →
  `running:true, mode:watchdog, watch_enabled:true` — **no `/restart` needed** (Defect 1).
- **B** (`manual-status-after-stop.json`): after stop + PATCH false → top-level AND
  `watcher.watch_enabled` both **false**, `running:false` (Defect 2). queue 0/0.
- **C** (`maintenance-dry-run.json`): retire dry-run matched **50** real `HB INSURANCE RENEWALS`
  cards (`by_policy.deferred=50`), `retired:0` — **no DB/file mutation**.
- **D** (`manual-d-self-index-guard.txt`): isolated temp-DB demo — `scan_vault_notes` indexes a
  normal note but skips the `Source Notes/` card (no recursive source work).
- `queue-before-after.txt`: 0/0/0 throughout — **no live queue drain**.

### Live-mutation posture
- **No live DB mutation performed.** The queue was empty (0/0) before and after; no retire `apply`
  was run on the live DB (apply/`delete_files` are proven by unit tests on temp DBs). 
- **No markdown note files deleted.**
- Config PATCHes (watch true→false) were made for validation and the live `obsidian_mcp_config.json`
  was restored **byte-identical** (sha `4348fe4e…`).
- Watcher was started briefly then stopped; it is **OFF** at end (config `external_source_watch_enabled=false`).

## Known limitations / follow-ups
- Retire matches the exclusion ∪ deferred source classes; bespoke per-class rules beyond path-parts
  are future work. "Retired" is the legal `stale` status (no new enum value).
- Deferred manual `generate_source_card` is intentionally allowed (operator override); only auto
  paths skip.
- No maintenance-op UI (operator-API only, given its destructive `delete_files` option).
