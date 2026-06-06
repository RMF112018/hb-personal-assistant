# 175 — FastAPI Dashboard Read Models (Prompt 07 / UI-07)

**Objective:** implement the first set of read models/endpoints for the simplified CM-first dashboard hierarchy per Prompt 07. Do not implement separate top-level domain dashboards. Compose existing domain analytics (procore projections, action/cost/schedule/freshness exposure, document/email/calendar intelligence, second-brain marts/gates/proofs/coverage, table inventory) into the 8 required dashboard surfaces:

- Today
- Projects Portfolio / All Projects
- Individual Project Overview
- Project Meetings
- Project Field Operations
- Project Cost & Time
- My Items
- Admin / Data Confidence (supporting)

## Required Endpoints (implemented)

- `GET /api/today`
- `GET /api/projects/portfolio`
- `GET /api/projects/all/overview`
- `GET /api/projects/{project_key}/overview`
- `GET /api/projects/{project_key}/meetings`
- `GET /api/projects/{project_key}/field-operations`
- `GET /api/projects/{project_key}/cost-time`
- `GET /api/my-items`

All added inside the existing optional FastAPI shell (`create_app` in `src/hb_assistant/construction/analytics/api.py`) using the established lazy-import + `role_dependency` + viewer posture (del role) + guardrails + FORBIDDEN redaction patterns from Prompts 02-06. No new top-level domain route trees or mounted apps. Viewer+ (read-only advisory metadata + badges); no operator/admin gating required for these surfaces.

## Composition Strategy + Catalog Mapping

Builders live on `AnalyticsService` (service.py) and reuse:
- `_project_metric` / `_metric_from_call` + `_empty_metric` for "requires_*" placeholders (status + reason_code + limitations + advisory language).
- Existing narrow projectors (`_procore_freshness`, cost_exposure, overdue_queue/action signals, schedule_exposure, recent_changes, etc.) and second-brain evaluators (gates, observability, automation_health, coverage_parity, no_writeback, table_inventory).
- `project_source_coverage_mart`, procore live records, construction source/sync state, document cards/classification candidates, email matches/thread summaries/review queue, calendar event index + meeting prep, etc.
- Freshness: reuse/extend patterns from `ConnectionSetupService.get_project_sync_freshness` + `procore_freshness.build_freshness_report` + `evaluate_observability`; overall + per-source badges.
- Confidence: per-metric "source_backed" / "not_available" + limitations; page-level "confidence_summary" with badges (coverage, sync_freshness, data_quality_gates, financial_completeness, etc.).

Metric selection prioritizes the revised 135-metric catalog (`docs/evidence/future-fastapi-analytics-dashboard-metrics-catalog/02-metrics-catalog.json` + `05-readiness-and-implementation-priority.md`):
- Top 20 / role lists + `dashboard_placement` + "ready_now" vs "requires_*".
- Representative ready_now surfaced directly (e.g. OPS-002/009/015/033/041/049/056/064/070/081, ADC-001, etc.).
- requires_read_model / requires_minor_read_model / requires_new_mart emitted as explicit status + reason_code + "Advisory signal only..." limitations (no over-claim).
- All advisory-only (catalog guard language + response "advisory_notes"; "makes_determination": false).

No new schema (reuse V5+ tables and marts). `_project_keys` continues to drive per-project loops (procore_live_records primary; tolerant of empty).

## Response Contract (10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md)

Every dashboard response includes:
- page/dashboard ID (surface)
- generated timestamp
- freshness/confidence summary (badges as supporting context)
- metric cards
- attention items
- sections
- drilldown references
- source/read-model names (dotted paths or "procore_freshness + source_sync_state + coverage_mart")
- advisory language where applicable
- empty/stale/error states

Every metric item includes:
- metric ID (OPS-*, ADC-*, HYB-* from catalog)
- user-facing name
- value (narrow projection)
- unit/format
- freshness context
- confidence/context badge
- source/read-model names
- advisory language
- drilldown target

No raw bodies, raw document text, raw prompts/responses, tokens, signed URLs, secrets, or PEMs (enforced by existing `_FORBIDDEN_KEYS` + test FORBIDDEN lists + guardrail "no_raw_sensitive_response_fields").

User-facing language is construction-native and advisory-only. No dry-run/apply/execute terminology.

## Guardrails

Every response carries `_guardrails()` (extended for 07):
- read_only, local_first, no_cli_shellout, no_external_writeback, sensitive_field_values_excluded, makes_determination: false, advisory_only: true, freshness_and_confidence_badges: true, no_raw_sensitive_response_fields: true.

Role dep remains (viewer default); surfaces are read-only.

## Validation

- New dedicated test: `tests/test_fastapi_analytics_dashboard_read_models.py` (FastAPI-optional, mirrors connection/keywords/governance style: `_client` -> (TestClient, db), FORBIDDEN + `_assert_safe`, viewer GETs for all 8 return 200 with correct surfaces/guardrails/metric IDs/badges/advisory, no forbidden markers, role smoke (invalid -> 403), empty-project degradation (unavailable states + reason), store post-action inspection where applicable).
- `tests/test_fastapi_analytics_app_shell.py` updated: exact OpenAPI paths set now includes the 8 `/api/*` routes.
- Existing analytics tests (service boundary, connection, keywords, sync-governance) + relevant store tests continue to pass (additive builders only; prior surfaces unchanged).
- Post-edit verification (see session): targeted pytest (new test + all `test_fastapi_analytics_*.py` + store filters), safe `-m "not integration and not live and not manual"` subset, ruff check+format on changed analytics + tests, mypy on analytics (respect pyproject partial scope), any affected guard proofs (additive, no schema impact).

## Cross-References

- Prompt: `docs/planning/fastapi-analytics-dashboard-implementation-package/prompts/Prompt_07_OPERATIONS_ANALYTICS.md`
- Read models spec: `.../10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md` (hierarchy, composition table, contract)
- Metrics + readiness: `docs/evidence/future-fastapi-analytics-dashboard-metrics-catalog/02-metrics-catalog.json` + `05-readiness-and-implementation-priority.md` (135 total, Top lists, ready_now vs requires, advisory language, dashboard_placement)
- Implementation sequence: `.../17_IMPLEMENTATION_SEQUENCE.md` (Phase UI-07)
- Backend design: `.../09_FASTAPI_BACKEND_DESIGN.md` (route families; reuse of internal read models through dashboard surfaces)
- Related: `.../07_AUTOMATED_SYNC_AND_FRESHNESS.md` (freshness badges), navigation_model + 11_FRONTEND_UI_STRUCTURE (simplified hierarchy), prior arch notes 172-174, 00_PACKAGE_MANIFEST (hard non-goals)
- Current shell/service: `src/hb_assistant/construction/analytics/{api,service,connection_setup}.py` + tests (Prompts 02-06 patterns)

This change is additive, local-first, metadata-only, and fully contained within the optional `analytics-ui` surface and existing construction store/migration discipline. No frontend (UI-08+ later), no Daily Brief file wiring (Prompt 10), no live data paths, no external writes, and no impact on core CLI or second-brain phases beyond read composition of already-gated artifacts. All prior guardrails and the "advisory-only / no raw / no determinations" posture are preserved.