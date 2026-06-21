# Forecast UI — Phase 6: Runtime Config Wiring (evidence)

**Stamp:** 20260621T040000Z · **Branch:** `feature/forecast-ui-phase6-runtime-wiring`
(off `feature/forecast-ui-phase5-review-surfaces` @ `9612205e`) · **Status:** uncommitted (awaiting authorization)

## What this phase delivers

The five forecast UI surfaces (Phases 1–5) resolved their filesystem roots only from `HB_FORECAST_*`
env vars set transiently in tests/smokes, so the running app served no real data. Phase 6 adds a
persistent app-support JSON settings file (`<app-support>/analytics/forecast_runtime_config.json`)
as a **third resolution layer behind the env vars**, an operator/admin settings surface to view
status and set the roots, and fail-closed validation — **no schema change, no CFR change, read-mostly**.

### Resolver precedence (per root)

`explicit constructor arg > env var > settings-file value > None`

Env beats the settings file so every existing test that `monkeypatch.setenv(...)` then constructs a
service with no args stays green; `None` at the bottom preserves the prior fail-closed → 503 behaviour.
Validation is **not** duplicated — the resolver returns the raw value; the existing service validators
remain the single fail-closed source of truth at use-time.

| Root | env var | required for |
|---|---|---|
| package_roots | `HB_FORECAST_PACKAGE_ROOTS` | catalog, review, eval baselines |
| data_root | `HB_FORECAST_DATA_ROOT` | run center, external eval |
| runs_root | `HB_FORECAST_RUNS_ROOT` | run center (write; must be outside data_root) |
| eval_root | `HB_FORECAST_EVAL_ROOT` | external eval (write; must be outside data_root) |
| db_path | `HB_FORECAST_DB_PATH` | config viewer, eval baselines (read-only) |
| cfr_src | `HB_FORECAST_CFR_SRC` | run center (optional; bundled default) |

### Redaction posture & admin carve-out

`find_redaction_leaks` flags any absolute path; every forecast response must pass it. Therefore:
- `GET /api/forecast/runtime/status` (**viewer**) returns booleans + coded blockers only — never paths.
- `GET /api/forecast/runtime/config` (**admin**) echoes the raw configured paths — the single,
  deliberate, documented carve-out (admin-gated; the page uses it to pre-fill the edit form).
- `POST /api/forecast/runtime/config` (**operator**) validates + persists, returning the
  redaction-safe status (never echoes the submitted path).

### Critical fail-closed cross-check

`resolve_eval_root` only guards "eval-root not under data-root" against the **env** data root. When
`data_root` comes from the settings file that guard is blind, so `save_runtime_config` independently
re-checks that `runs_root`/`eval_root` are not under the **resolved** data root and refuses the write
(nothing persisted) otherwise. Unit-tested.

## Validation summary

- **Backend (Phase 6 suites):** `test_forecast_runtime_config.py` + `test_fastapi_forecast_runtime.py`
  + `test_fastapi_analytics_app_shell.py` → **22 passed** (`test_output.txt`).
- **Env-var contract regression:** catalog/run/external/browser forecast suites all green.
- **Lint/type:** `ruff check` + `mypy` clean on `forecast_runtime_config.py`. (`api.py` is not in
  strict ruff scope; its pre-existing `B904` pattern is matched, not changed.)
- **Frontend:** `typecheck`, `copycheck`, `build` all clean; new page test 3/3 (full vitest: the only
  failures are the pre-existing `SettingsPage.test.tsx` ×5).
- **CFR subrepo:** **565 passed**, unchanged (`cfr_test_posture.txt`).
- **Live read-only smoke** (`live_untouched_proof.txt`): with a temp settings file (NOT the real
  app-support config path) pointing at the live Tropical data root + live DB, and **no** env vars set,
  all 10 read-only surfaces returned **200**, **zero redaction leaks**, data-root listing SHA
  **identical before == after**, live DB **WAL size 0**. This proves the settings file alone wires
  real data through with no live writes.

## Notes / honest caveats

- **Live DB is schema v61, not v60.** The Phase 4/5 handoff assumed v60 (v61 migration committed but
  unapplied); the live DB has since been migrated to v61 (8 empty external-forecast tables) by an
  earlier operation — **not** by Phase 6. The smoke's `before == after` confirms Phase 6 changed
  nothing (`db_schema_version.txt`).
- **Pre-existing failures are not Phase 6's** (`preexisting_failures.txt`): 2 documented env-sensitive
  tests, plus 7 CFR phase10–14 tests that fail only because the working tree contains an **uncommitted
  v62 Procore migration** from a separate workstream (synthetic DBs now report 62 vs a hardcoded 61).
  That workstream and the recurring phase-08b/08c evidence side-effects are **excluded** from the
  Phase 6 commit (`git_state.txt`).
