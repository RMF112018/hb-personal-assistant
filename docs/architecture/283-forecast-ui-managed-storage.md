# ADR 283 — Forecast UI: app-managed runtime storage

- **Status:** Accepted
- **Date:** 2026-06-21
- **Builds on:** ADR 278 (launch bootstrap), Implementation Phase 6 runtime config

## Context

ADR 278 auto-provisioned write-roots via launcher env injection, but operators still had to
manually configure read-roots (packages, data, database) through absolute-path forms. That is
appropriate for advanced overrides, not first-run setup.

## Decision

1. **Managed layout under Application Support** (via `PathPolicy`):
   - `forecast/packages`, `forecast/data`, `forecast/runs`, `forecast/evaluations`,
     `forecast/config-proposals`, `forecast/imports`
   - `db/hb-personal-assistant.sqlite` (existing app DB)
   - `analytics/forecast_runtime_config.json`

2. **Single bootstrap entry:** `ensure_forecast_managed_storage()` in `forecast_bootstrap.py`
   (FastAPI lifespan + launcher readiness). It ensures dirs, seeds missing settings keys,
   migrates the managed DB, and creates valid write-roots.

3. **Resolver precedence unchanged:** explicit > env > settings-file > managed_default.

4. **Legacy preservation:** existing settings/env values are never overwritten on bootstrap;
   only missing keys are seeded. Admin **Reset** (confirm required) is the explicit migration path.

5. **HTTP affordances:**
   - `POST /api/forecast/runtime/repair` — operator/admin
   - `POST /api/forecast/runtime/reset` — admin + `confirm: true`
   - `POST /api/forecast/runtime/config` — admin-only advanced override

6. **UI:** default surface is **Local data storage** readiness; manual paths live in collapsed
   **Advanced settings** (admin-only).

## Consequences

- Fresh install/launch reaches forecasting UI without entering absolute paths.
- Status payloads remain path-free; admin config echo remains the path-bearing carve-out.
- Launcher no longer injects forecast write-root env defaults (bootstrap + settings seed cover it).