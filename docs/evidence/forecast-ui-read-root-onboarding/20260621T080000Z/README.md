# Evidence — Forecast UI Read-Root Onboarding

**Phase:** Forecast CLI→UI product, Read-Root Onboarding ("finish just works")
**ADR:** `docs/architecture/279-forecast-ui-read-root-onboarding.md`
**Runbook:** `docs/runbooks/forecast-ui-launch-bootstrap.md` (read-root onboarding section)
**Date stamp:** 20260621T080000Z

## What shipped

Guides the operator to configure the read-roots (package_roots / data_root / db_path; cfr_src
optional) so catalog/config/external-eval go ready, and makes "ready" meaningful.

- **Backend (additive):** `forecast_runtime_config._db_advisory()` — non-blocking `mode=ro` probe
  returning integers only (`schema_version` + `config_snapshot_count`), merged into the `db_path`
  status entry. Mirrors `forecast_config_catalog`'s probe; returns `{}` on any error; never changes
  `db_blocker`/validity/`surfaces_ready`. `package_roots` already carried `count`.
- **Frontend:** `components/forecast/forecastRuntimeCopy.ts` (shared labels/blocker copy + READ_ROOTS
  + `rootAdvisory`), `hooks/useForecastReadiness.ts`, `components/forecast/ForecastReadinessPanel.tsx`
  (checklist + advisory + role-aware "Configure data sources" link; renders nothing when ready).
  `ForecastingPage` renders the panel + a "Data sources" header link; config/run-center/external-eval
  not-configured states get a "Configure data sources →" CTA (via `EmptyState` `actions`).

## Proof files

- `backend_test_output.txt` — `test_forecast_runtime_config` + `test_fastapi_forecast_runtime` +
  app-shell: **27 passed**. Covers advisory present/absent/graceful, `find_redaction_leaks == []`
  with the advisory, and unchanged `set(roots)` + `surfaces_ready` exact assertions.
- `live_readonly_smoke_proof.txt` — `SMOKE_OK`: unconfigured → no advisory + fail-closed; db_path =
  the **real live config DB** (mode=ro) → advisory `schema_version=61, config_snapshot_count=1`, zero
  redaction leaks, **live DB byte-unchanged**.
- `frontend_proof.txt` — copycheck clean, build clean, full vitest `5 failed | 97 passed` (the 5 are
  the pre-existing SettingsPage suite; new `ForecastReadinessPanel.test` + all forecast page tests
  pass).
- `cfr_test_posture.txt` — CFR subrepo **565 passed** (no CFR change).
- `db_schema_version.txt` — no DB/migrator/schema change; `LATEST_SCHEMA_VERSION = 61`.
- `preexisting_failures.txt` — the 5 SettingsPage failures, unrelated.
- `git_state.txt` — scoped change list (explicit pathspec; no Procore/08b/08c churn).

## Guardrails preserved

- Structural redaction: advisory is integers only (live smoke asserts no leaks over the real DB
  path). Admin echo remains the only path-bearing carve-out.
- Fail-closed + read-only: probe opens `mode=ro`, never blocks status, graceful-degrades to `{}`.
- Additive: no new HTTP route; root key set + `surfaces_ready` unchanged; no DB/schema change.
- All new copy business-facing + path-free (copycheck enforced).
