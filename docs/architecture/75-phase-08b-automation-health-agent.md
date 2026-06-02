# 75 — Phase 08B: Automation Health Agent + status surface

**Phase:** 08B (Automation Delivery & Observability) — Prompt 03
**Schema:** V28 (reused; no migration)
**Status:** Implemented. Deterministic, offline, read-only; no external delivery, no alert emitted,
metadata-only emit-gated receipt.

## Problem

Prompt 02 shipped the 08B substrate (V28 agent receipts, the automation policy seed with a
health-check list + structured reason codes, and `phase-08b-gates` with a deferred
`automation_execution` gate) but no executor. There was no way to actually run the seeded health
checks or surface runtime health.

## Design

### Automation Health Agent — `construction/second_brain/automation_health.py`
A deterministic, offline, read-only evaluator driven by the policy seed
(`load_phase_08b_automation_policy_seed()` → `health_checks.checks`). It runs four checks, each
reusing an existing primitive, and **never migrates or writes** during evaluation:
- `path_readiness` — `PathPolicy.ensure_db_ready(return_report=True)` (default path) or an inline
  parent-writable + sqlite-openable probe for an explicit db_path.
- `store_readiness` — DB connectable + a `schema_migrations` table present.
- `schema_at_latest` — `SQLiteMigrator(db).current_version() == LATEST_SCHEMA_VERSION`.
- `daily_brief_handoff_durable` — `sqlite_master` check for `daily_brief_handoff_lines`.

Models (`extra="forbid"`, no-raw): `HealthCheckResult` (check, status `ok|degraded`, reason_code,
detail — detail validated to carry no forbidden tokens) and `AutomationHealthStatus` (overall_status,
reason_code, checks, policy_version, schema_version, degraded_checks, generated_utc). Reason codes
come from the seed vocabulary: failing checks → `HEALTH_CHECK_FAILED`; overall `RUN_OK` /
`RUN_DEGRADED`.

Entry points: `evaluate_automation_health(*, db_path=None)` (pure read-only);
`run_automation_health(*, db_path=None, emit_receipt=False)` (evaluates, then — only when
`emit_receipt` — persists a metadata-only V28 `second_brain_agent_run_receipts` row via the existing
`build_agent_run_receipt` + `write_agent_run_receipt`, agent_id `automation_health_agent`, run_kind
`health_check`); `build_automation_health_proof()` (deterministic proof on a temp migrated DB).

### Status surface — `cli/second_brain.py`
New `automation` sub-app under `second-brain` + read-only command:
`second-brain automation health [--json] [--emit-receipt/--no-emit-receipt]`. Read-only by default
(`emit_receipt=False`); echoes overall status, per-check results + reason codes, schema version, and
`agent_run_id` (None unless emitted). Exit `0` when healthy, `3` when degraded. No `main.py` change.

### Gate wiring — `data_quality.py` + `phase_08b_data_quality_gates.json`
`automation_health` added to `PHASE_08B_GATE_NAMES` + the gates contract `required_fields`, evaluated
as a `_proof_gate("automation_health", build_automation_health_proof())` → `pass`. The
`automation_execution` and `launchd_install` gates remain `deferred_not_blocking` (retries, weekend
gating, real launchd install still pending).

### Reconstruct-determinism fix (carried in)
While running the full suite, a latent non-determinism in the Prompt-01 `read_daily_brief_handoff`
surfaced: it ordered the reconstructed top-level `source_refs` by the random
`daily_brief_source_ref_id`, so a multi-ref round-trip was flaky. Fixed to `ORDER BY rowid`
(insertion order = write order = context order), making reconstruction deterministic.

## Guarantees / invariants

- Health evaluation is read-only (no migration, no writes); receipt persistence is emit-gated (off
  by default). No external delivery; the agent records health locally and never sends an alert.
- Receipts metadata-only (status + reason code; nine `CHECK(=0)` guards + `extra="forbid"`). No raw
  content. Runtime artifacts outside the repo. No schema change (V28 reused).

## Known limitations

- The agent runs the four seeded checks; retry/backoff, weekend gating, and real launchd install
  execution remain deferred (`automation_execution` / `launchd_install` gates stay
  `deferred_not_blocking`).
- `path_readiness` for an explicit db_path uses an inline probe (parent-writable + sqlite-openable)
  rather than the full `ensure_db_ready` report (which targets the default path).
