# 02 — Worker / Scheduler / Watcher / Vault-Write Inventory

Re-confirmed against `origin/main` @ `704f59c8`. **No code changed since N8** — this is a verification that the gates N8 installed are intact on the clean base. All citations are `origin/main` file:line.

## Background-execution paths and their gates

| # | Path | Where (file:line) | Trigger | Gate | Default under `HB_NAS_RUNTIME=1` |
|---|---|---|---|---|---|
| A | Quality poll loop | `construction/analytics/api.py:768` | app lifespan | `not disable_workers` | **OFF** (forced) |
| B | Source watcher init/start | `construction/analytics/api.py:776-802` | app lifespan | `not disable_workers` + `external_source_watch_enabled` (default `False`, `obsidian_mcp/config.py:129`) | **OFF** (forced) |
| C | Source-root registration | `construction/analytics/api.py:781` | app lifespan | `external_source_index_enabled` (default `True`) gated by `not disable_workers` | **OFF** (forced) |
| D | On-demand watcher routes | `construction/analytics/api.py:2588` (`/start`), `:2607` (`/restart`), `:2615` (`/test-event`) | HTTP | `_nas_watch_guard` → `nas_on_demand_watch_allowed` (`config/db_storage_guard.py:44`) | **REFUSED** (`NAS_ON_DEMAND_WATCH_BLOCKED`) unless `HB_NAS_ALLOW_WATCH=1` |
| E | Bounded ingestion drain | `obsidian_mcp/source_indexer.py:494` (`drain_queue`), scan `:348` | one-shot MCP `rebuild_source_index` | manual one-shot; storage guard `assert_db_storage_allowed` (`api.py:729`) | manual only |
| F | Source-card generation | `obsidian_mcp/source_notes.py:896` (`generate_source_card`) | MCP tool | `source_card_generation_enabled` + write policy | manual only |
| G | Vault markdown write | `obsidian_mcp/mutations.py:155` (`_write_policy_enabled`) | card/patch write | `writes_enabled` **and** `vault_markdown_write_enabled` (both default `False`, `config.py:95-96`) | **OFF** |
| H | Mac scheduler (launchd) | `scheduler/backends/launchd.py`; label `scheduler/backends/__init__.py:48` | OS launchd | `profile.scheduler_enabled`; separate OS process, not started by the FastAPI factory | not started on NAS |

## Gating flags (defaults verified)

- `HB_NAS_RUNTIME` — unset by default; `="1"` forces workers/watcher/poll off (`resolve_background_worker_disable`, `construction/schedule_clean_db/diagnostics.py:15`, wired `api.py:709-722`) **and** restricts DB paths to `/volume2/personal-assistant/…` even against `HB_DB_STORAGE_GUARD=permissive` (`db_storage_guard.py:41`). Baked in `deploy/nas/Dockerfile:25`, `compose.yaml:32`.
- `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS` — unset by default (workers ON in dev); `="1"` disables (`diagnostics.py:11`); **required** for NAS MCP serve (`nas_mcp/guards.py:16`). Baked in `Dockerfile:28`, `compose.yaml:33`.
- `HB_NAS_ALLOW_WATCH` — unset by default (on-demand watcher refused under NAS); `="1"` permits, ownership then resting on the lease (`db_storage_guard.py:44-53`).

## Single-writer primitives (present)

- **Watcher lease** — `obsidian_mcp/source_watch.py:63`; acquire `:107`, degraded `watcher_not_owner` `:119`, token redacted from `status()` `:284`; TTL 900s; host/pid stamped; rows in `source_intelligence_state`.
- **Run no-overlap lock** — `construction/second_brain/run_registry.py`; `acquire_run_lock:191` (atomic `O_CREAT|O_EXCL`, `0600`), host-stamp `:212`; reason codes `RUN_OVERLAP_BLOCKED` / `STALE_LOCK_RECLAIMED` (prior token hashed); locks dir `<app_support>/locks`.

## Source-identity primitive (V99)

- `source_id_for` (`obsidian_mcp/source_index_repository.py:35`) folds `source_root_key` into the file id; V99 migration (`store/migrator.py:17` `LATEST_SCHEMA_VERSION=99`; reconcile `:8664`) enforces `UNIQUE(source_kind, source_root_key, rel_path)` and remapped all existing ids across 8 FK'd tables.

## Verdict

Inventory matches N8's; every background path is gated and default-off under NAS runtime. No drift in the gating code on the clean base. Proven live-safe by the tests in `03`.
