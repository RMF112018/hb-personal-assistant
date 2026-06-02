# 77 — Phase 08B: Run Registry, Run-Step Ledger & No-Overlap Locking (Prompt 05)

**Status:** Implemented (additive). Schema **V29** (two new tables); package stays `1.3.0`.
**Baseline:** atop `c1eefe8` (08B Prompt 04; 08A closeout `954a518` is ancestor).
**Scope:** Durable run-accounting substrate — an atomic no-overlap file lock, a run registry, and a
run-step ledger — plus a new proof-backed `run_registry_locking` data-quality gate. Distinct from
the still-deferred retry/backoff/weekend executor (`automation_execution` stays deferred).

## Context

The V1 `assistant_runs` ledger records a run's start/finish, but the `MorningRunOrchestrator`'s
13 stage results were **ephemeral** (returned in evidence JSON, never persisted), and there was
**no cross-process overlap guard** anywhere (only SQLite WAL + busy_timeout). This prompt adds the
durable substrate the future automation executor will consume.

## Design

New module `construction/second_brain/run_registry.py`:

- **No-overlap lock (atomic file).** `acquire_run_lock` creates `<app_support>/locks/<lock>.lock`
  with `os.open(O_CREAT|O_EXCL|O_WRONLY, 0o600)`. The payload is metadata-only
  (`{token, run_kind, pid, acquired_utc, expires_after_seconds}`). A live lock → `status=blocked,
  reason_code=RUN_OVERLAP_BLOCKED` (no write, **no deletion**). A lock older than
  `stale_lock_seconds` (default 3600) → reclaimed (`STALE_LOCK_RECLAIMED`) recording the prior
  token **hashed** (`prior_token_sha`, sha256[:16]), never raw. `release_run_lock` removes the
  file only when the on-disk token matches; a mismatch → `LOCK_RELEASE_TOKEN_MISMATCH` (retained,
  diagnosable). `read_run_lock` is read-only (held / stale / absent). `now` and `locks_dir` are
  injectable for deterministic tests. **SQLite is not the exclusion mechanism.**
- **Run registry (V29 `second_brain_run_registry`).** Emit-gated metadata-only rows
  (`run_kind / status / reason_code / lock_token / lock_status`, a nullable `assistant_run_id`
  **bridge** to the V1 ledger, `step_count`, `dry_run`). Nine no-raw/no-writeback guard
  `CHECK(col = 0)` columns.
- **Run-step ledger (V29 `second_brain_run_steps`).** Per-step metadata rows
  (`step_name / step_order / status / reason_code / detail`); lock acquire/reclaim/release events
  are recorded here (the hashed prior token lands in `detail`). FK → registry `ON DELETE CASCADE`;
  nine guard columns.
- **Coordinator** `coordinate_no_overlap_run` — acquire → register → record the declared steps →
  finish → release. Demonstrates the substrate without executing the real pipeline; on a live lock
  it returns `RUN_OVERLAP_BLOCKED` without registering or releasing.
- **`build_run_registry_locking_proof()`** — drives the gate. Because field/column names
  legitimately contain the substring `token` (`lock_token`), the proof's no-raw scan walks
  **values only**, never schema key names.

`PathPolicy.get_locks_dir()` resolves `<app_support>/locks` (outside the repo); the service
`mkdir`s it lazily and it is deliberately **not** added to `ensure_dirs` specs (to avoid
ensure_dirs report churn).

### Gate / policy / CLI

- `data_quality.py`: new `run_registry_locking` proof-gate → **pass**; added to
  `PHASE_08B_GATE_NAMES` + the gates contract `required_fields`. `automation_execution` stays
  `deferred_not_blocking` (retry/backoff/weekend executor unbuilt). phase-08b-gates → **8 pass /
  0 warning / 0 fail / 1 deferred**.
- Policy seed `no_overlap_locking` + `run_registry` sections + reason codes, mirrored in the
  automation-policy and data-quality-gates contracts. `deferred_surfaces` corrected to just
  `["automation_execution"]` (the Prompt-04 `launchd_install` flip was already a pass).
- CLI `second-brain automation`: `run-registry-status`, `run-lock-status` (read-only),
  `run-lock --mode dry_run|apply` (dry-run default).

## Guardrails

No external writeback/delivery/raw content; registry + step rows metadata-only with nine guard
columns; the prior lock token is hashed (never raw) on reclaim; lock files live outside the repo
(`<app_support>/locks/`); apply-capable `run-lock` is dry-run by default. Schema V1-V28 untouched;
`table_count` 144→146; both tables added to the no-writeback scan scope (`safety._PHASE_08A_TABLES`).

## Known limitations / next

- `automation_execution` (retry/backoff orchestration, weekend gating, full executor) stays
  deferred — the next 08B prompt, which will consume this registry + lock substrate.
- The `assistant_run_id` bridge column is present but not yet populated by the legacy
  `MorningRunOrchestrator` (left untouched); wiring it is future executor work.
- Lock liveness is time-based (stale TTL), not PID-liveness probing — sufficient for the
  single-machine launchd + manual-CLI posture.
- **Schema blast radius:** a future V30 must update the `146` literals in
  `test_data_quality_table_inventory.py`, `test_phase_08a_schema_v26.py`,
  `test_phase_07d_data_quality_gates.py`, `test_phase_08b_schema_v28/v29.py` + the lifecycle
  `table_count`.
