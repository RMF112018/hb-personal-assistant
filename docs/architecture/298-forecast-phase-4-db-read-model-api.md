# ADR 298 — Forecast Phase 4: DB-backed read-model API (run-output V63 + decision-support V66)

## Status

Accepted.

## Context

Phase 3 added the gated live-write for the forecast run graph (`forecast_runs` anchor → V63
run-output → V66 decision-support), but `/api/forecast/*` only surfaced package files and the V60
config snapshot — the persisted V63/V66 data had no read path. This phase adds the read-only,
DB-backed read-model API a UI can consume.

## Decision

New read-only service `analytics/forecast_run_readmodel.py`
(`ForecastRunReadModelService`) mirroring the Phase-2 `forecast_config_catalog` precedent:
`mode=ro` connection, fail-closed (`_assert_ready`, schema ≥ 66), `surface` + `guardrails`,
live-DB resolution via `forecast_runtime_config.resolve_db_path`. Four additive routes under a
distinct **`/api/forecast/db/`** prefix (kept separate from the existing file-based
`/api/forecast/runs`), viewer-readable, in `analytics/api.py`:

- `GET /api/forecast/db/projects/{project_key}/outputs` — output headers (newest first).
- `GET /api/forecast/db/outputs/{output_id}` — header + budget_codes/risks/monthly/probability/
  changes/staffing.
- `GET /api/forecast/db/outputs/{output_id}/decision-support` — maturity / data-availability /
  confidence scorecards (+factors) / method-eligibility / model-selection.

### Redaction (key design point)

`forecast_dto.find_redaction_leaks` flags `run_stamp` (`\d{8}_\d{6}`), `absolute_path`,
`module_path`, etc. The CFR `run_id` is stamp-format and the output-header `raw_json`/`source_path`
carry stamps + paths — so the service **never emits `run_id`, `raw_json`, or `source_path`**.
Instead it SELECTs a whitelist of business-safe columns, renders timestamps as friendly dates
(`_friendly_utc`), and navigates by the hash-based **`output_id`** (`fout-<hex>`, leak-free).
`read_decision_support` takes an `output_id` and resolves the `run_id` server-side (never emitted).

### Semantics

- Read-only; never writes. Fail-closed `503` on missing/unreadable DB or schema < 66.
- **Graceful-empty**: a migrated-but-unpopulated DB returns `200` with empty lists — the tables
  stay empty until an operator runs the Phase-3 gated write, then these endpoints light up.
- `404` on unknown `output_id` (detail/decision-support); `403` on invalid role.

## Consequences

- The persisted run-output + decision-support is now queryable via the API; unblocks the UI phase.
- **No schema / migration / count change**; only `analytics/api.py` is shared with the schedule
  session and the change is one additive forecast-route block (distinct prefix) — clean merge.
- The two new `raise HTTPException` sites match the adjacent `_forecast_config_call` idiom (the
  file is not ruff-clean-gated; B904 is the established local pattern).

## Verification

`tests/test_fastapi_forecast_run_readmodel.py`: list/detail/decision-support payloads;
`guardrails.read_only`; redaction-safe (`find_redaction_leaks == []`, no `source_path`, no
stamp-format `run_id` in any body); graceful-empty `200`; unknown `output_id` `404`; missing DB
`503`; invalid role `403`. Existing forecast API tests unaffected; ruff clean on the new service.
