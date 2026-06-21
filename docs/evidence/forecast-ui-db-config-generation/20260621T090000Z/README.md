# Evidence — Wire the Comprehensive Generator to Consume Live DB Config

**Phase:** Forecast CLI→UI product, DB-config-backed generation
**ADR:** `docs/architecture/280-forecast-ui-db-config-backed-generation.md`
**Date stamp:** 20260621T090000Z

## What shipped

The comprehensive forecast generator now CONSUMES the live config snapshot, so a promoted config
drives generation (`config_snapshot_consumed: True`) instead of only updating the viewer.

- **CFR:** `materialize_forecast_config_snapshot_readonly` (mode=ro; shared `_materialize` core) +
  `workflows/forecast_db_config_backed_generation.py` (snapshot select → RO materialize →
  materialization-fidelity gate → predecessor/cost-frequency guards → run comprehensive with scoped
  `CFR_CONFIG_ROOT` → deterministic report) + CLI `forecast-db-config-backed-generate`.
- **hb:** `HB_FORECAST_DB_CONFIG_RUN_ENABLED` opt-in + `surfaces_ready["db_config_run"]`;
  `ForecastDbConfigRunService` + DTO (consumes the live config DB at `PathPolicy().get_db_path()`,
  read-only, into an isolated runs-root; coded refusals → friendly messages; redacted record); routes
  `POST/GET /api/forecast/runs/db-config` (+ `{run_id}`) registered before the `{run_id}` catch-all.
- **frontend:** "Generate from live config" Run Center action + a "Source" column.

## Safety model

The gate is **materialization fidelity** (re-import + re-snapshot → `snapshot_sha256` + `item_count`
match the live snapshot's stored values), NOT generator-output parity — because a promoted edit
legitimately changes the output. Live config DB is opened `mode=ro` only; writes confined to the
isolated runs-root; no DB/schema change.

## Proof files

- `cfr_workflow_tests.txt` — new workflow + CLI tests: **9 passed** (happy path, fidelity-failure
  refusal, cost-frequency guard with data-root-untouched assertion, missing predecessor, unsafe
  work-root, RO-materialize-no-write, CLI rc0/rc3).
- `hb_focused_tests.txt` — db-config route + runtime-config + runtime + app-shell: **35 passed**
  (role gating, opt-in 503, not-configured 503, unknown-run 404, route ordering,
  `find_redaction_leaks == []` on all payloads, surfaces_ready + OpenAPI allowlist lockstep).
- `frontend_proof.txt` — full vitest **98 passed / 5 failed** (the 5 are the pre-existing SettingsPage
  suite; new Run Center action test + all forecast page tests pass; copycheck + build clean).
- `cfr_test_posture.txt` — CFR subrepo full suite **565 passed** (RO helper added; proofs unchanged).
- `live_readonly_smoke_proof.txt` — `SMOKE_OK` against the REAL live config DB: latest snapshot
  (`tropical-phase16-live-config-20260619T085305Z`, 194 items, 6 materialized files), fidelity passed,
  **live DB byte-unchanged** (also resolves the CSV round-trip canary against real config).
- `db_schema_version.txt` — no DB/migrator/schema change; `LATEST_SCHEMA_VERSION = 61`.
- `git_state.txt` — scoped change list (explicit pathspec; no Procore/08b/08c churn).

## Notes

- ruff clean on the new CFR + hb modules; mypy clean on the new modules (analytics is not in strict
  mypy scope — not claimed beyond the new modules).
- The Phase 17–20 proofs were intentionally NOT switched to the RO materialize helper (a fresh
  `mode=ro` open of a temp WAL DB without `-shm` breaks their fixtures); the RO helper targets the
  live DB and is covered by the live smoke. Recorded in the ADR.
- model_controls / monthly / probability consumers (already proven by Phases 17–19) can be wired the
  same way in a follow-up.
