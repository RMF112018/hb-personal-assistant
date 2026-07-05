# 03 — Default-Off + Single-Writer + Source-Identity (Re-Verification on Clean Base)

All proofs run against **tmp/temp scratch DBs** on the Mac (`.venv/bin/python -m pytest`, `PYTHONPATH` pinned to the N8A worktree `src`). **No live NAS data touched.** This re-verifies that the N8 hardening code is intact on the clean `origin/main` base — it does not re-run the live NAS proofs (04–07 already PASS; referenced in `04`–`07`).

## Command

```
PYTHONPATH=<worktree>/src .venv/bin/python -m pytest \
  tests/test_nas_default_off_gating.py \
  tests/test_obsidian_source_watch_ownership.py \
  tests/test_source_identity_v99_migration.py -q
```

## Result — `23 passed`

| Suite | Tests | Result | Proves |
|---|---|---|---|
| `test_nas_default_off_gating.py` | 6 | **passed** | `resolve_background_worker_disable` truth table (NAS-alone forces workers off); `nas_on_demand_watch_allowed` (dev allowed / NAS refused / `HB_NAS_ALLOW_WATCH=1` allowed); health surface renders `background_workers_forced_off_by_nas_runtime` |
| `test_obsidian_source_watch_ownership.py` | 11 | **passed** | second watcher on same DB refused (`watcher_not_owner`, `is_owner=False`), 1st stays owner; lease DB error fails closed (no 2nd writer); owner records hostname for cross-host attribution |
| `test_source_identity_v99_migration.py` | 6 | **passed** | V99 `UNIQUE(source_kind, source_root_key, rel_path)`; id remap folds `source_root_key`; same rel_path under different roots → distinct ids (no collision) |

Matches N8's per-suite counts (6 + 11 + 6). Environment: Python 3.14, `.venv` from the main checkout.

## Scheduler / launchd

The scheduler is a separate OS process (`scheduler/backends/launchd.py`) not started by the FastAPI factory (compose runs only the API factory). The Mac-side `com.hb.personal-assistant.scheduler.production` agent is loaded-but-idle and targets the Mac DB — the residual single-writer concern, carried as an **N8B/N9 cutover action item** (see `01` §C and `../live-20260705T075807Z/04-mac-scheduler-status.md`). N8A does not modify it.

## Verdict

**PASS.** Default-off posture, single-writer lease/lock, and V99 source-identity are intact on the clean base. No code change required by N8A.
