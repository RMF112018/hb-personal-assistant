# 02 — Worker / Scheduler / Watcher / Ingestion / Automation / Vault-Write Inventory

Verified against the N8 worktree (`recon/nas-code-n7` base, origin/main + reconciled N7). Line numbers are current.

## Background-execution paths and their gates

| # | Path | Where | Trigger | Gate today | Default |
|---|---|---|---|---|---|
| A1 | Quality poll loop (`_quality_poll_loop`) | `construction/analytics/api.py:741,754` | app startup (`asyncio.create_task`) | `not disable_workers` | **ON** unless disabled |
| A2 | Source-root registration | `api.py:774` (`SourceIndexRepository.register_source_roots`) | app startup | `not disable_workers` AND `external_source_index_enabled` | index **True** |
| A3 | External-source watcher (thread + watchdog Observer) | `api.py:779,782`; `obsidian_mcp/source_watch.py:82` | app startup | `not disable_workers` AND `external_source_watch_enabled` | watch **False** |
| B | Watcher worker thread + `Observer()` | `source_watch.py` (daemon `source-watcher`) | `SourceWatcher.start()` | watcher **lease** (see below) | — |
| C | One-shot rebuild drain thread (`source-rebuild-drain`) | `obsidian_mcp/source_indexer.py request_rebuild` | on-demand (rebuild route) | `external_source_index_enabled` | — |
| D | On-demand watcher routes (`source-watch/start\|stop\|restart\|test-event\|recover-stuck`) | `api.py:2544–2585` | HTTP (operator role) | `require_operator_role` only | **bypasses boot gate** via `_resolve_source_watcher` (`api.py:2531`) |
| E | Scheduler OS process (`daily-source-refresh --loop`/`--if-due`) | `launcher/service.py:223–236` | launcher/launchd | `profile.scheduler_enabled` only | **not** gated by the workers env flag |
| F | Automation executor (daily brief) | `construction/second_brain/automation_executor.py` | CLI, on-demand | dry-run default; apply needs `confirm && !dry_run`; acquires run lock | writes off by default |
| G | launchd daily-brief agent | `construction/second_brain/launchd_scheduler.py` | macOS launchd | policy `dry_run_install_only` | install disabled |
| H | Vault writers (`create_note`/`patch_note`) | `obsidian_mcp/mutations.py:277,356` | on-demand (MCP/operator) | `writes_enabled && vault_markdown_write_enabled` | writes off by default |

## Gating flags (current behavior)

- **`HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS`** (`api.py:697`, `schedule_clean_db/diagnostics.py:12`): default **workers ON**; only `"1"` disables. Scope = **A1–A3 lifespan only**. Also **required** for `nas_mcp` serve (`nas_mcp/guards.py:20`).
- **`HB_NAS_RUNTIME`** (`config/db_storage_guard.py:41`, `api.py:692`): today gates **only the DB storage guard** (restricts DB paths to `/volume1/personal-assistant/…`, ignores `HB_DB_STORAGE_GUARD=permissive`) and fail-closed startup posture (`api.py:674,732`). **Does NOT force workers/scheduler/watcher default-off** — this is the Phase 3a gap.

## Single-writer primitives (present)

- **Watcher lease** (`source_watch.py:38,77,102,105`; `source_index_repository.acquire_watcher_lease`): opaque `owner_token` (uuid), 900s TTL, `roots_hash` folds in `db_path`. Fail-closed: `watcher_lease_error` / `watcher_not_owner` degrade (no observer/thread). `stop()` releases only if owner. **Coordinates only when both processes open the SAME SQLite DB** (lease rows live in that DB).
- **Run no-overlap lock** (`run_registry.py:180,190`; `<app_support>/locks/*.lock`, `O_CREAT|O_EXCL`, 0o600): live lock → `RUN_OVERLAP_BLOCKED` (no deletion); stale (>`stale_lock_seconds`, default 3600) reclaimed with hashed prior token. **Coordinates only across processes sharing the SAME app-support locks dir.**

## Gaps for N8 (drive Phase 3)

1. **Default-off (3a):** `HB_NAS_RUNTIME=1` does not force A1–A3 off; relies on the separate env flag. Scheduler (E), on-demand routes (D), launchd (G) not covered by either flag under NAS runtime.
2. **On-demand bypass (3a):** routes in D lazily construct+start a watcher even when boot workers were disabled.
3. **Cross-host single-writer (3b):** lease/lock coordinate only within a shared DB / app-support. Mac launchd scheduler (`com.hb.personal-assistant.scheduler.production`, Mac DB) and a NAS scheduler are uncoordinated; overlap risk if source roots point at the same synced folders.
4. **Source identity (3c):** `source_id_for` omits `source_root_key` → cross-root collision (proven by `test_same_rel_path_in_two_roots_collides_on_source_id`).
