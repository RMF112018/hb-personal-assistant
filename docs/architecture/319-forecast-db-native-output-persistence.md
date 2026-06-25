# 319 — Forecast DB-native output persistence & writeback (Phase F)

- Status: accepted
- Date: 2026-06-25
- Phase: Forecast Run Center remediation — Phase F (DB output persistence)
- Related: ADR 317 (DB-native generation engine), ADR 318 (BudgetDetails cost-basis inputs), ADR 314 (DB-native contract seam), ADR 313 (fail-closed boundary)

## Context

Phases E/E2 (ADR 317/318) produce a typed, path-free in-memory DB-native forecast result
(`DbNativeForecastResult.public()`) from DB source data with no source/context/analysis package. But
`POST /api/forecast/runs/db-native` stayed fail-closed (`db_native_generation_not_implemented`) and
persisted nothing — there was no package-free way to land the result in the DB. Phase F adds that
persistence and wires the route, so a DB-native comprehensive forecast becomes a durable run output.

The existing live-write path (`forecast_run_output_persistence_service.persist_run_output`) is
package-based (it drives the CFR `run_controlled_live_db_run_output_projection` backup→temp→replace→
certify workflow). DB-native must persist **without** any package, manifest, or CFR artifact.

## Decision

### Package-free persistence module (`forecast_db_native_output_persistence.py`)

Maps `result.public()` → the v63 `planned` dict and reuses the existing idempotent
`output_repository.apply_plan` inside one transaction (`open_connection` + `transaction`). No new
schema, no repo methods, no package paths, no file IO.

- **v63 only:** `forecast_outputs` (header), `forecast_output_budget_codes` (one row per forecast
  line), `forecast_output_risks` (engine-emitted risks only — never synthesized to fill the table),
  `forecast_output_narratives` (one row per assumption). `monthly / probability / changes /
  commitment_exposure / staffing / schedule_phasing` are emitted empty (the financial-spine
  comprehensive result has no rows for them). **No v66 decision-support rows** — that surface is not
  expanded in Phase F.
- **Deterministic, idempotent `output_id`:** `fout-` + sha256(`project_key|generator_kind|
  source_snapshot_id`) — derived from project identity, never the random `run_id`, so a repeated
  request UPSERTs a single header (latest-wins) rather than duplicating. `run_id` is the established
  `uuid4().hex[:12]` shape set as the `forecast_outputs.run_id` column; **no `forecast_runs` anchor row
  is written** (mirrors the HB-side `output_projection_engine.project_run_output`, which also persists
  via `apply_plan` only).
- **Bounded, sanitized payloads:** `forecast_outputs.raw_json` holds only a bounded envelope
  (status / result_code / window / maturity / confidence / summary / provenance) — never the source
  snapshot, context, raw engine input, paths, or package names. Per-line / per-risk / per-assumption
  `raw_json` holds the already-sanitized engine detail dict. Money stays canonical Decimal strings.

### Mandatory certification preflight (before any write)

`certify_db_native_result` runs against the **built planned rows** (not just the engine result) and
must return clean or nothing is written (`db_native_output_certification_failed`, no partial rows):
request_id/project_key present; generator_kind supported (comprehensive); status generated/degraded;
forecast_lines present; every line has `budget_code_key`; per valued line `final ≥ actual` and
`cost_to_complete ≥ 0`; all persisted money fields Decimal-parse; provenance present; and a
`find_redaction_leaks` pass over the planned payload (paths / run-stamps / module paths / private
URLs). The write is one transaction — any error rolls back atomically (`db_persistence_failed`).

### Gate posture (route)

- Default runtime posture is **no write**: the route is gated by the existing default-OFF
  `resolve_run_output_db_write_enabled()`. Disabled → curated `run_output_db_write_disabled` refusal;
  nothing computed is silently dropped. The legacy `db_native_generation_not_implemented` is no longer
  returned by this route.
- Operator-enabled posture computes via the read-only adapter and persists to `resolve_db_path()` —
  including the managed app DB — but only after the certification preflight passes.
- No package fallback: on unsupported kind (`db_native_generator_kind_unsupported`) or insufficient
  basis (`db_native_insufficient_basis`) it fails with a coded reason and writes nothing.
- Lineage: on success the request-ledger row records `run_id` (a safe public identifier).

### Testing & live-DB safety

Temp SQLite DBs only (autouse temp app-support root); the real managed DB is never touched in tests.
Tests prove the write path against the resolved DB path. Production writes require the explicit
operator flag. A certified backup/replace managed-write workflow (CFR-style) for DB-native remains
deferred to a later phase.

## Consequences

- DB-native comprehensive forecasts persist as v63 run outputs and are readable by the existing run
  read-models and prior-run lookup. Non-comprehensive kinds and no-basis projects remain unsupported
  and write nothing. No schema / migrator / table-count / hb_assistant-vs-CFR boundary change.
