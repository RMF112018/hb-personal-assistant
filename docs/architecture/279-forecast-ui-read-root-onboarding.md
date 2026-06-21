# ADR 279 — Forecast UI: read-root onboarding (guided readiness + advisory)

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast CLI→UI product, Read-Root Onboarding ("finish just works")
- **Builds on:** ADR 278 (launch bootstrap — write-roots auto-provision), Phase 6 runtime config wiring
  (`forecast_runtime_config.py` + `ForecastRuntimeSettingsPage`), Phase 2 config catalog
  (`forecast_config_catalog.py`).

## Context

The launch bootstrap (ADR 278) made the **write**-roots auto-provision, but the **read**-roots —
`package_roots`, `data_root`, `db_path` (cfr_src optional) — point at the live project inputs and must
be configured by the operator. The settings page (`/forecasting/runtime`) already had a full status
table + edit form, but nothing linked to it, and every forecast surface dead-ended on a friendly
"not configured" `EmptyState` with no path to fixing it. "Ready" also only meant *the path exists* —
not that the DB/folder actually holds forecast content.

## Decision

A frontend-led onboarding over the existing `GET /api/forecast/runtime/status`, plus one small,
redaction-safe backend advisory enrichment.

### Backend: non-blocking advisory probe (additive only)

`forecast_runtime_config._db_advisory(raw)` opens the configured `db_path` `mode=ro` and returns
**integers only** — `schema_version` (from `schema_migrations`) and `config_snapshot_count` (from
`forecast_config_snapshots`) — merged into the `db_path` status entry via the existing
`_root(..., **extra)` hook. It mirrors the proven probe in `forecast_config_catalog` without
importing the heavier service. It **never raises** (returns `{}` on any error: missing / locked /
old-schema / config-tables-absent) and **never** changes `db_blocker`, validity, or `surfaces_ready`.
`package_roots` already carried a `count`. The status root **key set** and `surfaces_ready` dict are
unchanged (both asserted exactly in tests). No new route; no DB/migrator/schema change.

**Redaction:** the advisory is ints only — never the DB path or a snapshot name — so the status
payload still passes `find_redaction_leaks`. The admin echo (`GET /runtime/config`) remains the only
path-bearing carve-out.

### Frontend: readiness panel + per-surface CTAs

- `components/forecast/forecastRuntimeCopy.ts` — shared `ROOT_LABELS` / `BLOCKER_COPY` (extracted from
  the settings page so the two never drift) + `READ_ROOTS` (the read-roots to onboard, with the
  surface each unlocks) + `rootAdvisory()` (builds "N forecast packages found" / "Ready · schema vNN,
  M config snapshots" from the redaction-safe status).
- `hooks/useForecastReadiness.ts` — thin react-query wrapper over the status (mirrors
  `useOnboardingReadiness`).
- `components/forecast/ForecastReadinessPanel.tsx` — a checklist of the read-roots with friendly
  status + advisory counts + what each unlocks, and a role-aware `Configure data sources` link to
  `/forecasting/runtime`. Renders nothing when all read-roots are ready.
- `ForecastingPage` renders the panel and adds a "Data sources" header link; its 503 `EmptyState` and
  the config/run-center/external-eval not-configured states get a `Configure data sources →` CTA
  (reusing `EmptyState`'s existing `actions` slot).

The settings page keeps ownership of the actual edit form; onboarding only guides and links to it.
No global app first-run hook (forecast config must not block the whole app); no separate wizard.

## Consequences

- A freshly launched app guides the operator from any forecast surface to configure the read-roots,
  and "ready" now confirms real content (package count, DB schema + config-snapshot count).
- All copy is business-facing and path-free (`copycheck` enforced).
- Live read-only smoke confirmed the advisory reports schema v61 / 1 config snapshot against the real
  config DB with zero redaction leaks and the live DB byte-unchanged.
