# ADR 278 — Forecast UI: live app launch bootstrap (ensure-dirs + readiness)

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast CLI→UI product, Live App Bootstrap/Launcher
- **Builds on:** the existing cross-platform launcher (`hb-assistant launcher dev/production`,
  `LauncherService`), ADR-era Phase 6 runtime config wiring (`forecast_runtime_config.py`), and the
  Phase 1–E2 forecast surfaces.

## Context

A full process launcher already exists: `hb-assistant launcher dev/production` spawns the backend
(`uvicorn ...create_app --factory`), the frontend, and the scheduler. But **nothing bootstraps the
forecast roots when the app launches.** `create_app()` was a pure factory with no startup hook; the
launcher preflight only checks ports; and `forecast_runtime_config.py` validation is intentionally
**non-mutating** (no `mkdir` anywhere). So a freshly launched app served no real data on the
write-backed surfaces (run-center / external-eval / config-edit) until someone hand-edited
`<app-support>/analytics/forecast_runtime_config.json`, and surfaces only reported blockers at
request time with no launch-time visibility.

Goal: a documented local run entrypoint that, on launch, ensures the forecast write-roots exist,
validates roots fail-closed, surfaces a redaction-safe readiness report, and serves all forecast
surfaces with **no live writes** — while keeping manual `uvicorn` runs and the test suite strictly
fail-closed.

## Decision

### 1. Single mutation site: `forecast_bootstrap.ensure_forecast_roots()`

A new module `construction/analytics/forecast_bootstrap.py` is the **only** place allowed to create
forecast roots. It resolves the 3 **write-roots** (runs / eval / config-edit) via the existing
resolvers, runs the existing `_write_root_blocker` check, and `mkdir(parents=True, exist_ok=True)`
only when a root is **configured AND has no blocker** (absolute, outside the resolved `data_root`,
parent creatable). It is idempotent and returns the `build_runtime_status()` shape plus a coded
`created` list of write-root **keys** (never path strings). `forecast_runtime_config.py` stays pure
(its non-mutating contract and tests are untouched); `forecast_bootstrap` depends on it
one-directionally.

**Read-roots are never created** (package_roots / data_root / db_path / cfr_src). They point at the
live Tropical inputs and must be configured explicitly — fail-closed.

### 2. FastAPI lifespan startup hook

`create_app` now passes `lifespan=_forecast_lifespan` to `FastAPI(...)`. The lifespan calls
`ensure_forecast_roots()` and **swallows all exceptions** — the bootstrap is informative and must
never block startup (mirrors the optional-surface degrade posture). This covers manual
`uvicorn ...create_app --factory` launches, not just the launcher. With nothing configured (the
test/manual default) it is a no-op: `TestClient(create_app(...))` without a context manager does not
trigger lifespan at all, and with the context-manager form the hook runs but creates nothing.

### 3. Launcher auto-provisions write-root defaults (explicit launch path only)

`LauncherService._child_env()` now injects 3 forecast write-root env vars defaulted under
`<profile.app_support_root>/analytics/forecast/{runs,eval,config-edit}` — for **both** dev and
production — but **only when the key is set neither in the inherited env nor in the profile's
settings file** (operator config always wins). Read-roots are never defaulted. The launcher injects
env only; the directories are created by the backend lifespan hook (single mutation site).

**Why this is consistent with fail-closed roots, not a violation:** the defaults are isolated
work-roots under app-support, structurally outside any `data_root` (the `under_live_data_root` check
still runs), and auto-defaulting happens **only in the launcher** — never in `create_app`, never in
the resolvers — so manual `uvicorn` and the test suite stay strictly fail-closed.

### 4. Redaction-safe readiness in `start()`

`LauncherService.start()` attaches a non-fatal `forecast_readiness` block (skipped for `--plan` so a
dry plan stays side-effect-free). It applies the child env to `os.environ` within a scoped patch
(restored in `finally`) so the parent resolves roots exactly as the spawned backend will, then calls
`ensure_forecast_roots()`. The block is path-free (coded enums + root keys); a failure degrades to a
coded `unavailable` status. Launch never fails on a not-ready surface.

### No new HTTP route

Readiness rides the existing `GET /api/forecast/runtime/status`; no route is added, so the exact-set
OpenAPI allowlist test is untouched. `build_runtime_status()` / `surfaces_ready` are byte-identical,
preserving the existing exact-set assertions. No frontend change (it already GETs the status surface
and sends `X-HB-UI-Role`). No DB/migrator/schema change.

## Consequences

- `hb-assistant launcher dev --open` (or `production`) now serves the write-backed forecast surfaces
  out of the box; read-roots still require explicit configuration via the settings page.
- The bootstrap is idempotent and safe to run on every launch and every app start.
- Tests/manual `uvicorn` remain fail-closed; only the launcher auto-defaults write-roots.
