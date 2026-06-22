# Forecast UI polish — validation summary (2026-06-21)

## Scope

Product-grade polishing pass on forecasting frontend surfaces while preserving app-managed forecast runtime storage behavior (no normal-user absolute paths; repair/reset/admin advanced overrides intact).

## Commands and results

| Check | Command | Result |
|-------|---------|--------|
| ESLint | `cd frontend && npm run lint` | **PASS** (0 errors) |
| Typecheck | `cd frontend && npm run typecheck` | **PASS** |
| Build | `cd frontend && npm run build` | **PASS** (`dist/` produced) |
| Vitest | `cd frontend && npm run test -- --run` | **PASS** — 23 files, 105 tests |
| Backend | `PYTHONPATH=.../src python -m pytest tests/test_forecast_runtime_config.py tests/test_forecast_bootstrap.py tests/test_fastapi_forecast_runtime.py tests/test_fastapi_analytics_app_shell.py -q` | **PASS** — 44 tests |
| Smoke | `PYTHONPATH=.../src python -m scripts.smoke_local` | **PASS** |

### Non-blocking warnings (deferred)

- React Router v7 future-flag warnings in Vitest stderr
- Starlette/FastAPI `TestClient` / `httpx` deprecation warning in pytest

## Manual visual / API smoke (ports 8000 + 5173)

Servers started locally:

- Backend: `uvicorn hb_assistant.construction.analytics.api:create_app --factory --port 8000`
- Frontend: `npm run dev -- --port 5173 --host 127.0.0.1`

| Check | Result |
|-------|--------|
| `GET /` and `GET /forecasting` (Vite) | 200 |
| Forecast API surfaces (`projects`, `runs`, `config/snapshots`, `external/evaluations`, `runtime/status`) | 200 (operator role) |
| Runtime status payload — viewer/operator/admin | No `/Users/` or Application Support paths in JSON body |
| Normal UI path fields | Not shown by default (covered by `ForecastRuntimeSettingsPage.test.tsx`) |
| Advanced manual path override | Admin-only, collapsed (`Advanced manual path override`) |
| Reset confirmation | Admin-only with confirm (existing behavior preserved in tests) |

Screenshots: not captured in this pass (headless validation only).

## No-raw / redaction confirmation

- Forecast page tests assert no `\d{8}_\d{6}` run stamps and no `/Users/` in rendered text.
- Runtime status API probe (viewer/operator/admin): no filesystem paths in response body.
- Smoke harness: Prompt H hygiene checks passed (no raw/secrets in onboarding/DQ surfaces).
- Admin advanced panel still exposes path placeholders only when expanded (development/support carve-out).

## Files changed (forecast polish)

### New shared components

- `frontend/src/components/forecast/ForecastStatusPill.tsx`
- `frontend/src/components/forecast/ForecastPageChrome.tsx`
- `frontend/src/components/forecast/useEffectiveSelection.ts`
- `frontend/src/components/forecast/AdminPathOverrideForm.tsx`

### Updated surfaces

- `frontend/src/components/forecast/ForecastReadinessPanel.tsx`
- `frontend/src/components/forecast/forecastRuntimeCopy.ts`
- `frontend/src/pages/ForecastingPage.tsx`
- `frontend/src/pages/ForecastRuntimeSettingsPage.tsx`
- `frontend/src/pages/ForecastConfigPage.tsx`
- `frontend/src/pages/ForecastRunCenterPage.tsx`
- `frontend/src/pages/ForecastExternalEvalPage.tsx`
- `frontend/src/pages/ForecastConfigEditProposalsPage.tsx`
- `frontend/src/pages/ForecastPackagePage.tsx`
- `frontend/src/components/ui/ErrorBoundary.tsx`
- Corresponding `*.test.tsx` files for all forecast pages + readiness panel

### Related backend/storage (preserved from prior work on branch)

- `src/hb_assistant/construction/analytics/forecast_bootstrap.py`
- `src/hb_assistant/construction/analytics/forecast_runtime_config.py`
- `src/hb_assistant/construction/analytics/api.py`
- Associated tests under `tests/test_forecast_*` and `tests/test_fastapi_*`

## Known deferred polish items

- Playwright or browser screenshot regression suite for forecasting flows
- Richer charts/visualizations on package detail (monthly trend is bar-only)
- React Router v7 migration / future flags
- Starlette `httpx2` TestClient migration
- Full interactive browser walkthrough with screenshots (manual checklist validated via tests + API probe)
- Production packaging / hosted deployment polish

## PR readiness

**Ready for review** on forecasting UI polish scope: ESLint clean, typecheck/build/tests/smoke pass, guardrails preserved, evidence bundle present. Remaining items above are explicitly deferred and non-blocking.