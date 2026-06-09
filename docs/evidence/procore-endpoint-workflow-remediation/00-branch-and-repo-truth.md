# 00 — Branch & Repo Truth

Prompt: `00_REPO_TRUTH_AUDIT.md`. **No code changed in this step** (evidence only).

## Branch / HEAD snapshot

| Fact | Value |
| --- | --- |
| Base branch | `main` @ `f8439ca4aca55cc52bdb0e41d10d887f34a765e8` (== `origin/main`, clean, ff-only) |
| Working branch | `fix/procore-endpoint-contracts-and-persistence` (created off `main`) |
| `main` contains prior fix merge | Yes — `f8439ca4` is "Merge pull request #9 from RMF112018/fix/procore-live-refresh-degradation" |
| `fix/procore-live-refresh-degradation` | Fully merged — **0** commits ahead of `main` (`git log main..fix/procore-live-refresh-degradation` empty) |
| Untracked (not committed) | `config/config.yml` (gitignored on this branch), `docs/planning/**` packages |
| Latest migration | **V44**; canonical `procore_live_*` tables exist since V6/V7 |

## Branch comparison

- `experiment/phase-10-intelligence-daily-brief-remediation` (the tree's prior branch) is ahead of `main` on unrelated daily-brief intelligence work and **behind** `main` on the Procore live-refresh fix. Per README the correct base is `main`, which already carries the Procore fix. No newer unmerged Procore endpoint/scheduler branch exists → no reconciliation STOP.

## File-path map (the two Procore paths)

| Concern | Module |
| --- | --- |
| Scheduler entry | `src/hb_assistant/cli/scheduler.py` → `scheduler/runner.py` → `scheduler/daily_source_refresh.py` |
| Source-refresh orchestration | `src/hb_assistant/source_refresh/orchestrator.py` (`_procore_stage`) |
| **Legacy** request builder + writes | `src/hb_assistant/procore/sync.py` (`run_sync`) → `procore_synced_entities`, `procore_sync_watermarks` (and creates-but-never-writes `procore_sync_runs`/`procore_sync_errors`) via `store/repositories.py` |
| Legacy contract | `resources/config/procore_endpoint_contract.seed.yaml` |
| **Canonical** request builder + writes | `src/hb_assistant/procore/live_sync.py` (`run_live_sync`) + adapter registry `procore/endpoints.py` → `procore_live_records`, `procore_live_sync_runs`, `procore_live_sync_watermarks` via `store/procore_repositories.py` |
| Live gate | `src/hb_assistant/procore/live_gate.py` (`HB_PROCORE_LIVE=1`, strict pilot mapping) |
| GET-only transport | `src/hb_assistant/procore/http_client.py` (`_require_get`) |
| Downstream read models | `store/procore_operational.py`, `procore_freshness.py`, `procore_history.py`, `procore_cost_exposure.py`, `procore_schedule_exposure.py`, `procore_project_health.py`, `procore_action_queue.py`; `construction/issue_history/`, `construction/analytics/`, `construction/second_brain/daily_brief/`; `procore/obsidian_operational.py` — all read **`procore_live_*`** |
| Legacy readers | `procore/obsidian.py` (receipts), `procore/validate.py`, `construction/manifests/service.py` — read `procore_sync_*` |

## Specific questions answered

1. **Current `main` HEAD** → `f8439ca4`.
2. **Is `fix/procore-live-refresh-degradation` merged?** → Yes, fully (0 commits ahead).
3. **Newer Procore endpoint/scheduler branches?** → None unmerged/relevant.
4. **What does `scheduler run daily-source-refresh --environment production --json` execute?** → `cli/scheduler.py:run_cmd` → `SchedulerRunner.run_once` → `DailySourceRefreshJob.execute` → `SourceRefreshOrchestrator.run` → `_procore_stage` loops pilot projects calling `procore/sync.py::run_sync` (legacy path).
5. **Which path writes `procore_sync_*`?** → `procore/sync.py` (`procore_synced_entities`, `procore_sync_watermarks`). `procore_sync_runs`/`procore_sync_errors` are created but **not written** (DB count = 0/0).
6. **Which path writes `procore_live_*`?** → `procore/live_sync.py::run_live_sync` (canonical), invoked today only by manual `procore live sync`, **not** by the scheduler.
7. **Which downstream consumers query each path?** → Operational/freshness/history/analytics/daily-brief/issue-history/obsidian_operational read `procore_live_*`. Only `obsidian.py`/`validate.py`/manifests read `procore_sync_*`.
8. **Is `procore_sync_runs` created/written?** → Created (V1 helpers in `repositories.py`), **never written by the scheduler path** (DB count = 0).

## Initial risk list

- The scheduler writes the **legacy** path while every operational read-model consumes the **canonical** path → daily refresh has not been feeding the tables the product reads (live records last refreshed 2026-06-03 by manual runs).
- 7 of 10 daily-refresh endpoints fail at the API because the legacy request builder uses stale/incorrect routes and omits required scoping/date params (see `01`/`02`).
- Run/error ledgers for the legacy path are inert (count 0) → no endpoint-level run history from the scheduler.
- Remediation must preserve GET-only, redaction, `raw_body_persisted=0`, fail-closed live gate, and must not perform destructive migration.
