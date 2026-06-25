# 314 — Forecast generation: DB-native contract & routing boundary (seam only)

- Status: accepted
- Date: 2026-06-25
- Phase: Forecast Run Center remediation — Phase B (DB-native contract & routing boundary)
- Related: ADR 313 (DB-native generation boundary, fail-closed), ADR 303 (P3 DB-native model-input
  accessors); PR #137 (honest db-config failure surfacing)

## Context

ADR 313 made the DB-native *boundary* honest but left it **implicit**: true DB-native generation was
hidden behind an env flag (`HB_FORECAST_RUN_OUTPUT_DB_WRITE_ENABLED=1`) on the **db-config** route,
and the three real generation behaviors were bare strings (`"file_config"` / `"db_config"`) with no
type. Before the generation engine is built, the repository needs a precise, typed, testable
**contract** that distinguishes the three behaviors and gives true DB-native its own explicit,
fail-closed seam.

This ADR records a **route/contract seam only**. It does **not** claim DB-native generation exists.

## Current repo-truth

- `_persist_and_run(mode, body, role)` (`construction/analytics/api.py`) is the shared
  validate → record-request → branch → respond helper for all generation routes.
- The db-config route, when DB-output-write is enabled, calls
  `forecast_run_output_persistence_service.generate_and_persist(db_native_intended=True)`, which is
  **package-backed end-to-end** (`run_controlled_context_analysis_workflow(mode="file")` +
  `run_controlled_live_db_run_output_projection`, both requiring file `source_package`/
  `analysis_package` dirs) and fails closed with `db_native_generation_not_implemented` (ADR 313).
- There was no `GenerationMode` type; `generation_mode` was set from bare strings.

## Decision

1. **Three named, typed modes** — a new `GenerationMode(StrEnum)`
   (`construction/analytics/forecast_generation_modes.py`):
   - `FILE_CONFIG = "file_config"` — legacy file/package-backed run.
   - `DB_CONFIG_PACKAGE = "db_config"` — DB-config-backed **package** generation (consumes the live
     config snapshot; still package-backed, **NOT** DB-native). The value stays `"db_config"` for
     back-compat (request rows, API responses, frontend `generation_mode === 'db_config'` are
     byte-identical); the member name is the only disambiguation. `db_backed` is never a mode value.
   - `DB_NATIVE = "db_native"` — true DB-native generation + persistence.

2. **Explicit DB-native route + contract seam** — `POST /api/forecast/runs/db-native` (operator-
   guarded) routes through `_persist_and_run(mode=db_native)` to a new
   `forecast_db_native_generation_service.generate_db_native(...)`. The contract:
   - **Request** (`DbNativeGenerationRequest`, path-free): `project_key`, `generator_kind`,
     `forecast_start_date`, `forecast_cutoff_date`, `forecast_cutoff_date_basis`,
     `source_snapshot_id` (deterministic source-data provenance; optional in Phase B).
   - **Response** (`DbNativeGenerationResult`, path-free): `mode`, `request_status`, `db_persisted`,
     `failure_code`, `failure_message`, `persisted_output_ids`, `source_snapshot_id`.

3. **Fail-closed + package-free** — `generate_db_native` returns `request_status="failed"`,
   `failure_code="db_native_generation_not_implemented"` (single curated, path-free message reused
   from the persistence service via `failure_message_for`), `db_persisted=False`,
   `persisted_output_ids=()`. It **never** calls `_run_generation`, `generate_and_persist`,
   `ForecastDbConfigRunService.start_db_config_run`, the CFR context/analysis or live-write
   workflows, or any `package_resolution` helper, and imports none of them. There is no silent
   fallback to package generation.

4. **No behavior change to existing routes** — `/api/forecast/runs` and `/api/forecast/runs/db-config`
   are byte-compatible (`generation_mode`, `request_status`, `generator_kind`, failure behavior
   unchanged). The enum makes current behavior explicit; it does not alter it.

5. **`source_snapshot_id` is contract-only in Phase B** — returned by the fail-closed route but **not
   persisted**; no DB migration is added for it. Persistence is deferred to Phase C/F (which will use
   an existing column or a separately-scoped, low-risk schema path).

## Consequences

- The three generation behaviors are now distinct in code, on the wire (via the route), and in tests.
- True DB-native has an explicit, fail-closed, package-free home for Phase C/D/E/F to fill — instead
  of being an env-flag mode on the db-config route.
- Redaction is preserved: the request/response contract and the request-history DTO are path-free.

## Generation-mode boundary truths (normative)

- Package-backed generation is **legacy / bridge** behavior.
- DB-config-backed package generation is **not** DB-native.
- True DB-native generation **may not require** source / context / analysis packages at all.
- Human-readable exports are allowed **only as outputs after DB persistence**, never as required
  runtime inputs.

## Non-goals (deferred)

- DB-native calculation/persistence logic (Phase C/D/E), live-DB writes, source-package generation on
  the db-native path — all excluded; the seam stays fail-closed.
- Frontend wiring — no client function, label mapping, or UI consumes `/api/forecast/runs/db-native`
  yet (Phase C/D). The route is backend-only and unconsumed in Phase B.

## Remaining seams (Phase C/D/E/F)

- **C** — package-free DB-source context for sparse / zero-monthly-actuals projects.
- **D** — DB-native calculation + direct DB persistence (no file `source_package`/`analysis_package`).
- **E** — UI wiring (client call, `db_native` mode label) once the engine lands.
- **F** — resolve + persist `source_snapshot_id` provenance; certification proving no package
  dependency remains (per ADR 313's future-CFR list).

## Guardrails

- No live-DB mutation; no external calls; no user-facing package on the db-native path; no raw
  path / payload / secret leakage in API responses or DTOs.
