# 03 — Default-Off + Single-Writer + Source-Identity Hardening (Phase 3)

All proofs run against **tmp/temp scratch DBs** on the Mac (`.venv/bin/python -m pytest`, PYTHONPATH
pinned to the N8 worktree src). **No live NAS data touched.** Full NAS-runtime *startup* requires a
`/volume1` DB (storage guard) and is a live-NAS proof (deferred to Phases 04–07).

## 3a — Default-off on NAS

**Change:** `HB_NAS_RUNTIME=1` is now authoritative for the default-off posture.
- `resolve_background_worker_disable(nas_runtime, env_disabled)` (`schedule_clean_db/diagnostics.py`)
  forces workers off under NAS runtime even if `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS` was not set;
  wired into `_forecast_lifespan` (`analytics/api.py`).
- Health route now surfaces `background_workers_forced_off_by_nas_runtime` and `nas_runtime`.
- `nas_on_demand_watch_allowed()` (`config/db_storage_guard.py`) closes the on-demand bypass: the
  `source-watch/start|restart|test-event|recover-stuck` routes lazily start a watcher regardless of
  the boot gate — under NAS runtime they now return `NAS_ON_DEMAND_WATCH_BLOCKED` unless the operator
  opts in with `HB_NAS_ALLOW_WATCH=1` (ownership then rests on the watcher lease).

**Proof (`tests/test_nas_default_off_gating.py`, 6 passed):**
- `resolve_background_worker_disable` truth table — the NAS-alone case forces off (`disable=True, forced=True`).
- `nas_on_demand_watch_allowed` — dev allowed; NAS default refused; `HB_NAS_ALLOW_WATCH=1` allowed.
- Health surface renders the new fields (workers disabled, poll/watcher not started).

**Scheduler / launchd:** the scheduler is a separate OS process (`launcher/service.py scheduler`) gated
by `profile.scheduler_enabled`, and the daily-brief launchd agent is policy `dry_run_install_only`.
On the NAS neither is started by the FastAPI factory (compose runs only the API factory). The Mac-side
`com.hb.personal-assistant.scheduler.production` launchd agent is the residual single-writer concern —
see 3b + the preflight action item.

## 3b — Single-writer posture across Mac + NAS

**Existing (verified):** the watcher **lease** (`source_intelligence_state`) and the run **no-overlap
lock** (`<app_support>/locks/*.lock`, `O_CREAT|O_EXCL`) both fail-closed on a live different owner and
already serialize single-writer access **within a shared DB / locks dir**.

**Change:** host-stamp both so cross-host contention is *attributable, never silent*:
- `source_watch.py` — `owner_info["hostname"]`; `degraded_not_owner` logs `owner_host`.
- `run_registry.py` — lock payload `["hostname"]`.

**Proof (`tests/test_obsidian_source_watch_ownership.py`, 11 passed):**
- `test_second_watcher_runs_degraded` — a 2nd watcher on the same DB is refused
  (`watcher_not_owner`, `is_owner=False`, `running=False`), 1st stays owner.
- `test_lease_check_error_fails_closed` — a lease DB error degrades (no drain), never opens a 2nd writer.
- `test_owner_records_hostname_for_cross_host_attribution` — the active owner carries a hostname.

**Cross-host boundary (honest scope):** the lease/lock coordinate only when both hosts open the **same**
DB / locks dir. The NAS uses the canonical `/volume1/personal-assistant/app-support` DB + locks, so any
process against it is serialized. A **different-DB** competitor — the Mac launchd scheduler writing the
Mac app-support DB — is *not* lease-coordinated and can overlap **only if source roots point at the same
synced folders**. Resolution is operational + enforced by 3a's NAS default-off:
1. NAS is the sole owner of the canonical DB (3a forces NAS workers off; NAS is single-purpose).
2. Unload `com.hb.personal-assistant.scheduler.production` on the Mac before NAS scheduler cutover
   (preflight action item; requires Bobby, not done this session).
3. Any enabled job now has: ownership (lease/lock token + host), a lease/lock, an audit receipt
   (run registry / lock payload), and a stop command (`source-watch/stop`, `release_run_lock`,
   `deploy/nas/scripts/stop.sh` / `emergency-shutdown.sh`).

**Verdict:** single-writer holds within the canonical DB; the residual different-DB overlap is bounded
to the launchd action item. **Not a blocker** given NAS default-off + the operational constraint.

## 3c — Source-identity collision fix (full)

**Change:** fold `source_root_key` into the file `source_id` so the same rel_path under different roots
never collides / overwrites.
- `source_id_for()` file identity → `sha256(source_kind|file|<root>|rel_path)`; domain-link unchanged.
- `upsert_source_file` / `lookup_by_path` / `mark_deleted` thread `source_root_key`; indexer hot paths
  pass `root.source_root_key` (scan, delete-reconcile, drain).
- **Schema V99 migration** (`store/migrator.py`, `LATEST_SCHEMA_VERSION=99`): replaces
  `UNIQUE(source_kind, rel_path)` with `UNIQUE(source_kind, source_root_key, rel_path)` and remaps every
  existing file `source_id` across all **8** FK'd tables (sources/metadata/text/chunks/relationships/
  generated_notes/events/summaries) using `PRAGMA defer_foreign_keys=ON` (FK-consistent at commit).
  The id formula is **frozen (inlined)** in the migration. Safe bijective remap: the old
  `UNIQUE(source_kind, rel_path)` guarantees at most one row per rel_path, so no new collisions.

**Proof (`tests/test_source_identity_v99_migration.py` 6 + flipped collision test + head-row guard):**
- `test_source_id_folds_in_root_key` — distinct ids per root; domain-link identity unchanged.
- `test_distinct_roots_same_relpath_coexist` — both rows survive, each keyed to its own root.
- `test_same_root_upsert_is_idempotent` — one row per (root, rel_path).
- `test_v99_migration_remaps_old_colliding_ids_and_children` — a seeded pre-V99 old-id row + FK'd
  children (metadata, generated_notes) are remapped to the root-scoped id; `PRAGMA foreign_key_check`
  clean; old id gone; index swapped.
- `test_v99_migration_is_noop_when_already_root_scoped` — re-run is a stable no-op.
- Flipped `test_same_rel_path_in_two_roots_gets_distinct_source_ids` (was `_collides_`) — asserts
  distinct ids + per-root rows.
- `test_v99_migration_row_present` — head migration row `v99_source_identity_root_scoped`.

**Verdict:** source-identity collision is **ruled out** (derivation + composite unique index + backfill),
clearing that N8 stop-condition for the code path. Live-DB backfill on the NAS is a Phase 05/07 item.

## Consolidated result

`114 passed` across the N8-touched suites (identity/migration, default-off, ownership, schema-version,
pm-grade cards, watch, auto-generate, source-index repo, db-storage-guard, nas-mcp, nas-runtime-scaffold).

**Pre-existing failures (confirmed on the clean `recon/nas-code-n7` base, NOT from N8):**
`test_phase_08b_schema_v30/v34` (FTS5 tables absent from the older lifecycle contract in this env);
`test_automation_executor_service::test_proof_builder_passes` / `::test_p08_..._writes_md` (full
delivery pipeline / ollama-osascript dependent). Ruff: `SIM103`/`F821` on untouched lines of
`db_storage_guard.py` / `diagnostics.py` (the `F821` undefined `Path` in `build_db_diagnostics` is a
latent pre-existing bug on a cold path — flagged, not fixed, to avoid unrelated churn).
