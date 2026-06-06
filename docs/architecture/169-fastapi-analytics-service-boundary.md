# 169 — FastAPI Analytics Service Boundary (Prompt 01)

**Objective:** create the reusable application-service boundary for the future
FastAPI/UI analytics dashboard without adding FastAPI routes, frontend code, schema
migrations, dependency installs, live endpoint calls, or Typer command shell-outs.

## Boundary

Future UI route handlers should call
`hb_assistant.construction.analytics.AnalyticsService`. The service calls existing
Python read-model/domain builders directly and returns compact metadata summaries:
metric id, status, source function, confidence, limitations, guardrails, and counts.

Typer remains a CLI adapter only. UI code must not call `hb-assistant ...`, import
`hb_assistant.cli`, or use `subprocess`/`os.system` to reach analytics behavior.

## Services

`AnalyticsService(db_path: str | None = None)` exposes three Prompt 01 methods:

- `build_operations_summary()` — Top-20 operations-planning metrics backed by
  existing Procore/action/schedule/freshness read models where available; metrics
  that need new marts or minor read models are reported as `requires_read_model`.
- `build_admin_confidence_summary()` — data-confidence metrics backed by existing
  table inventory, gate, no-writeback, freshness, automation-health, and coverage
  evaluators.
- `build_metric_catalog_status()` — local planning-catalog metadata only. It does
  not expose the full catalog row set.

All methods are read-only and fail closed. Missing project data, stale schema, or
unavailable read models produce `unavailable` / `requires_read_model` status and
reason codes rather than readiness claims.

## Guardrails

The service is local-first and metadata-only. It does not make legal, financial,
safety, schedule, entitlement, claims, liability, approval, or readiness
determinations. It does not write to source systems, call live endpoints, persist
operator DB rows, write Obsidian files, open local files, or expose raw bodies,
prompts, responses, auth material, signed links, download URLs, arbitrary SQL, or
secret-like values.

## Validation

Prompt 01 adds focused tests in
`tests/test_fastapi_analytics_service_boundary.py` covering service construction,
metadata-only payloads, no CLI shell-out dependency, stale-schema degradation,
empty-project fail-closed behavior, and planning-catalog metadata loading.
