# 80 — Phase 08B: Daily Brief Job Health Monitoring (Prompt 08)

**Status:** Implemented (additive). Schema **V30 unchanged** (no new table); package stays `1.3.0`.
**Baseline:** atop `ed34c64` (08B Prompt 07; 08A closeout `954a518` is ancestor).
**Scope:** A read-only, deterministic job-health evaluator over the V26 `daily_brief_runs` ledger,
plus a new proof-backed `daily_brief_job_health` gate. `automation_execution` stays the only
deferred 08B gate.

## Context

The daily-brief job writes one `daily_brief_runs` row per run (`status` = `synthesized` healthy /
`blocked` degraded, plus `degradation_mode`, `review_tier`, `generated_utc`). The Prompt-03
automation-health agent covers the *runtime substrate* and Prompt-07 covers *source/retrieval
freshness*, but neither answers "is the daily-brief *job itself* healthy — on cadence, succeeding,
not degrading?" This prompt adds that focused observability surface.

## Design

New module `construction/second_brain/daily_brief_health.py` (read-only; injects `now`/`db_path`;
reuses `read_latest_daily_brief_runs`):

- `evaluate_daily_brief_job_health` examines the most recent runs:
  - no runs → `JOB_NEVER_RUN`;
  - latest run age > `max_age_hours` (default 36 — a daily 20:00 cadence) → `JOB_STALE`;
  - latest run `status` not in the healthy set (`{synthesized}`) **or** `degradation_mode` set →
    `JOB_DEGRADED`;
  - otherwise → `JOB_HEALTHY` (overall `ok`).
  It also reports the consecutive non-healthy streak from the newest run backward.
- `run_daily_brief_job_health(emit_receipt=...)` optionally persists a metadata-only V28
  `agent_run_receipt` (`agent_id='daily_brief_job_health_agent'`) — the only apply-capable path,
  off by default.
- `build_daily_brief_job_health_proof()` drives the gate across four isolated temp DBs (never-run /
  healthy / degraded / stale), with a values-only no-raw scan.

### Gate / policy / CLI

- `data_quality.py`: new `daily_brief_job_health` proof-gate → **pass**; added to
  `PHASE_08B_GATE_NAMES` + the gates contract `required_fields`. `automation_execution` stays
  deferred. phase-08b-gates → **11 pass / 0 warning / 0 fail / 1 deferred**.
- Policy seed: `daily_brief_job_health` section (`max_age_hours: 36`, `healthy_statuses:
  [synthesized]`, reason codes), mirrored in the automation-policy + data-quality-gates contracts.
- CLI `second-brain automation daily-brief-health` (read-only; `--emit-receipt` off by default;
  exit 0 on ok, 3 on attention).

## Guardrails

No schema change (V30/147 unchanged); the receipt reuses the V28 table (already in the no-writeback
scan scope). The evaluator reads only `daily_brief_runs` metadata columns; the only write is the
emit-gated metadata-only V28 receipt (off by default = dry-run posture). `degradation_mode` and
`detail` are validated against forbidden tokens. No external writeback/delivery; no raw content.
Phase 08A guardrails preserved (phase-08a-gates 8/1/0/3; no-writeback proof passes).

## Known limitations / next

- `automation_execution` stays deferred — the final executor consuming all 08B observability +
  substrate surfaces.
- Health keys off the latest run + a simple consecutive-streak count; richer SLA windows (e.g.
  rolling success rate over N days) can be layered on later.
- Cadence is a single global `max_age_hours`; per-mode (dry_run vs apply) cadence not differentiated.
