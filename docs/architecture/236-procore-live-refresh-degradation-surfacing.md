# 236 — Procore Live Source-Refresh: Degradation Surfacing + Apply Blockers

Status: fixed (branch `fix/procore-live-refresh-degradation`) · schema V44 (no migration) ·
local-only · no Procore/Graph writeback

## Symptom

`hb-assistant scheduler run daily-source-refresh --environment production --json` resolved the
correct production DB with Procore live enabled but returned `orchestrator_status: degraded`,
`counts.failed: 4`, `counts.planned: 0`, `inserted: 0` — while writing a receipt with `status: ok`.
Procore data had not changed since 2026-06-03 and the failure reasons were not discoverable.

## Root causes (a four-layer onion, each exposed by the layer above)

1. **Status masking (H/J).** `daily_source_refresh.execute()` set `status = "ok" if
   orchestrator_status in ("ok","degraded")`, and the receipt copied only the count totals — it
   discarded `summary["failures"]` and never called the orchestrator's `write_evidence()`. So a
   degraded run looked "ok" and its reasons were lost (in-memory only).
2. **Expired access token (B).** The cached Procore access token had expired ~53h earlier;
   `check_auth_status().ready_for_live_calls` is **presence-only** (token cache + secret present),
   so the live gate passed and the live-apply loop ran with a dead token. The refresh token was
   valid (`procore auth refresh` succeeded). *Operational fix: token refreshed.*
3. **Invalid environment default (A/D).** `ProcoreSyncCoordinator` defaulted `environment="prod"`
   and `run_sync` passes no environment; the only valid values are `"sandbox"`/`"production"`, so
   `get_environment_config("prod")` raised `Unknown environment: prod` for all 4 pilot projects
   before any API call — the original `failed: 4`.
4. **No live transport (F).** The coordinator built `ProcoreHTTPClient(transport=None)` **without
   `live_enabled=True`**, so with no injected transport every endpoint failed
   `transport_not_injected` (the `failed: 40` after layer 3 was fixed).

A fifth honesty gap: endpoint-level errors (`redacted_errors`) incremented `counts.failed` but did
**not** set `degraded`, so a run with 0 items and many endpoint errors still reported `ok`.

## Fixes

- **Diagnosability + honest status** (`scheduler/daily_source_refresh.py`, `scheduler/models.py`,
  `cli/scheduler.py`): persist the full redacted orchestrator summary via the existing
  `write_evidence()` (`evidence/scheduled/source-refresh-<env>-<date>-run<id>.json`); add receipt
  fields `failure_count`, redacted `failures[]`, per-stage `stages`, `procore_auth_status`,
  `next_operator_action`, `evidence_summary_path`. The wrapper `status` now mirrors the orchestrator
  (`ok|degraded|failed`) — never collapses degraded→ok. Manual runs exit **2 (degraded) / 1
  (failed)**; scheduler ticks keep exit 0 so unattended launchd success detection is unchanged.
  `scheduler status` surfaces resolved db/evidence paths, all three live-read gates, and the last
  run's status/failure_count. Token-shaped values are scrubbed defensively.
- **Apply blockers** (`procore/sync.py`, `procore/config.py`): coordinator default
  `environment="production"` (+ `"prod"` normalized to `"production"` in both the coordinator and
  `get_environment_config`); `_get_client()` passes `live_enabled=live_env_active()` so the real
  GET-only transport is built only when `HB_PROCORE_LIVE=1` (the scheduler arms it; tests keep the
  gate off and inject mocks).
- **Endpoint-error honesty** (`source_refresh/orchestrator.py`): a project whose sync receipt
  carries `redacted_errors` now marks the project and the run **degraded** and records a redacted
  endpoint-error sample in `failures[]` + the persisted evidence.

## Live proof (production DB, backed up first)

After the fixes a manual production run **persisted real data**: `procore_synced_entities` gained
**1185** rows (tropical 887, alton-hilltop-pbg 167, pga-modern-garage 131) and **12**
`procore_sync_watermarks` advanced — all timestamped 2026-06-09. The run reported `status: degraded`
(exit 2), `inserted: 1185`, `failed: 28` (7 endpoints × 4 projects), with `failures[]` naming the
remaining endpoint errors. Backup: `/tmp/hb-personal-assistant-before-procore-sync-*.sqlite`.

## Known follow-ups (separate, now visible — not masked)

- **7 endpoints/project still error** at the API: `list-projects` / `list-change-events` →
  HTTP 400 "Missing Project or Company ID"; `list-daily-logs` → 400 "Start/End Date required";
  `list-drawings` / `list-punch-items` / `list-prime-contracts` → 404. These are endpoint-contract
  parameterization issues (the contract doesn't pass the required project/company/date params for
  those endpoints). They are now surfaced as `degraded` with reasons, not masked.
- **Two Procore persistence schemas.** The daily orchestrator's `run_sync` (Prompt_09 `sync.py`)
  writes `procore_synced_entities` / `procore_sync_watermarks` / `procore_sync_runs`. The
  `procore_live_*` tables an operator may monitor (`procore_live_records`, `procore_live_sync_runs`,
  …) are written by a **different** path (`live_sync.py`) the orchestrator does not call. The
  "unchanged since 2026-06-03" observation was of the `procore_live_*` tables; the orchestrator was
  (and now successfully is) writing the `procore_sync_*` tables. Reconciling these two paths is a
  follow-up architecture decision, out of scope for this degradation fix.
- `procore_sync_runs` is not written by the coordinator (0 rows) even though watermarks/entities are
  — a minor receipt-completeness gap.

## Guardrails

GET-only Procore (no writeback); no Graph/M365 writeback; no cloud LLM; no schema migration; no
secrets/tokens/raw payloads in receipts, evidence, or logs (presence checks + defensive scrub).
Production DB backed up before the live run; `config/config.yml` is machine-local (gitignored).
