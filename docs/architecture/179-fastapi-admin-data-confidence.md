# FastAPI Analytics — Admin / Data Confidence (Prompt 11 / UI-11)

## Objective and Scope

Implement the Admin / Data Confidence support surfaces (Prompt 11 / UI-11) per the implementation package.

Admin / Data Confidence is **required but secondary**. It is a trust, governance, and troubleshooting layer. Primary screens (Today, Projects, My Items) remain construction-facing and show only compact badges + links ("View source & sync details → Admin", "Open Admin / Data Confidence"). Detailed diagnostics live exclusively here.

The 6 required sections (exact from 14_ADMIN_DATA_CONFIDENCE.md and Prompt_11):
- Source / Sync Health
- Workflow / Job Health
- Evidence / Guardrail Health
- Retrieval / AI Quality
- Permissions / Governance
- Data Completeness / Coverage

These are backed by the 35 admin_data_confidence (ADC-001…ADC-035) metrics defined in the metrics catalog (evidence_inputs/02-metrics-catalog(1).json and resources/json/metrics_catalog.json), with top-10 priorities and readiness notes in evidence_inputs/05-readiness-and-implementation-priority(1).md.

Backend surfaces (per 09_FASTAPI_BACKEND_DESIGN.md and 10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md):
- GET /api/admin (root aggregator/summary)
- GET /api/admin/source-sync-health
- GET /api/admin/workflow-job-health
- GET /api/admin/evidence-guardrails
- GET /api/admin/retrieval-ai-quality
- GET /api/admin/permissions-governance
- GET /api/admin/data-completeness

All responses follow the documented read-model contract (page/dashboard ID, generated timestamp, freshness/confidence summary, metric cards with id/name/value/unit/freshness/confidence badge/source/read-model names/advisory/drilldown target, attention items, sections, drilldown references, advisory language, empty/stale/error states, guardrails). No raw sensitive fields (bodies, prompts/responses, tokens, signed URLs, PEMs, secrets) are ever serialized.

Role: detailed views are admin-only (`can_access_admin_confidence` true only for admin per roles_permissions.json and 03_USER_ROLES_AND_PERMISSIONS.md). Construction users see compact badges and links on primary surfaces.

Heavy reuse of existing deterministic, read-only, guardrail-clean evaluators (phase_09_gates, second_brain.safety no-writeback/no-raw proofs, automation_health + daily_brief job health, freshness/observability, table_inventory, corpus_balance_mart/coverage_parity, source_sync_state + procore_freshness, MCP tool call/denial receipts, unsupported_claim_checks, memory_quality_review, etc.). These are already partially wired in AnalyticsService.build_admin_confidence_summary (ADC-001, ADC-008, ADC-013, ADC-015, ADC-018, ADC-031).

Post-change discipline (per user query + 16_/17_/Prompt_11/14_): update architecture documentation, run the appropriate verification suite, prepare a traditional commit (manifest title + Prompt 11 / UI-11 description), commit, and only output the commit summary + description as final assistant output.

Cross-refs: Prompt_11_ADMIN_CONFIDENCE.md, 14_ADMIN_DATA_CONFIDENCE.md, 09_FASTAPI_BACKEND_DESIGN.md, 10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md, 11_FRONTEND_UI_STRUCTURE.md, 12_UI_KIT_THEME_AND_COMPONENTS.md, 15_SECURITY_GUARDRAILS_AND_PRIVACY.md, 16_TESTING_VALIDATION_ACCEPTANCE.md, 17_IMPLEMENTATION_SEQUENCE.md (Phase UI-11), 03_USER_ROLES_AND_PERMISSIONS.md, resources/json/{metrics_catalog.json, navigation_model.json, roles_permissions.json}, evidence_inputs/{03-dashboard-blueprints(1).md, 04-fastapi-analytics-endpoints(1).md, 05-readiness-and-implementation-priority(1).md, 02-metrics-catalog(1).json}, prior architecture 176-178, and the existing AdminDataConfidencePage skeleton + navigation entry + "→ Admin" links from UI-08/09 work.

## The 6 Sections — What They Surface (verbatim intent from package)

From 14_ADMIN_DATA_CONFIDENCE.md + 03-dashboard-blueprints(1).md + 04-endpoints + metrics catalog:

- **Source / Sync Health**: source coverage, freshness, Graph delta, mailbox, calendar, blocked/review-routed items. (ADC-001 Project Source Coverage Confidence, ADC-002 Source Sync Freshness, ADC-003…007 Enabled Sources / Graph Delta Resume / Mailbox / Calendar / Items Blocked Or Routed To Review.)
- **Workflow / Job Health**: daily brief, automation, retry, no-overlap, and generated-output receipts. (ADC-008 Daily Brief Run Health, ADC-009 Automation Run Health, ADC-010…012 Recent Generated Output / Retry Backoff / No-Overlap Lock Health.)
- **Evidence / Guardrail Health**: data-quality gates, no-writeback/no-raw proofs, guardrail column coverage, schema confidence, evidence freshness. (ADC-013…018 Data Quality Gate Status, No-Writeback / No-Raw Proof Status, Guardrail Column Coverage, Schema Version Confidence, Evidence Freshness By Domain.)
- **Retrieval / AI Quality**: approved source manifests, vector/LlamaIndex/embedding readiness, evals, unsupported-claim checks, memory review. (ADC-019…025 Approved Source Manifest Coverage, Vector Index Readiness, LlamaIndex Configuration Readiness, Embedding Model Evaluation Status, Retrieval Evaluation Pass Rate, Unsupported Claim Risk Checks, Memory Quality Review Status.)
- **Permissions / Governance**: MCP calls/denials, permission posture, prohibited metric attempts, policy compliance. (ADC-026…030 MCP Tool Call Receipts, MCP Denied Operation Receipts, Permission Posture Warnings, Prohibited Metric Attempts, Policy Compliance Status.)
- **Data Completeness / Coverage**: table inventory, Procore endpoint data, financial completeness, document/correspondence coverage. (ADC-031…035 Full Table Inventory Coverage, Procore Endpoint Data Coverage, Financial Completeness Coverage, Document Intelligence Coverage, Correspondence Intelligence Coverage.)

Every metric carries data caveats: "Based on local SQLite/read-model truth and available source coverage; source confidence/freshness should be shown as supporting context." Sensitivity classifications and advisory language are defined in the catalog.

## Backend Implementation

Location: `src/hb_assistant/construction/analytics/` (consistent with Prompts 05-10 pattern; 09_ aspirational ui_api/ layout noted for future).

- Routes + Pydantic (api.py): 7 GET handlers under `/api/admin/*` (root + 6). require_admin_role for the detailed family. Lazy imports to AnalyticsService. Responses carry the full read-model contract + guardrails + presenter-style advisory.
- Service (service.py): build_admin_confidence_summary (pre-existing, wires 6 key ADC metrics via _metric_from_call to the evaluators) remains the root. Added 6 `build_admin_*_health()` methods that return section-specific rich payloads (metrics list with ADC ids, attention_items, sections, freshness, advisory_notes, guardrails, etc.). Heavy delegation to:
  - `second_brain.automation_health.evaluate_automation_health` (and daily brief job health patterns)
  - `second_brain.phase_09_gates.evaluate_phase_09_data_quality_gates`
  - `second_brain.safety.build_second_brain_no_writeback_proof`
  - `second_brain.freshness.evaluate_observability`
  - `data_quality.table_inventory.build_table_inventory_report`
  - `second_brain.corpus_balance_mart.build_coverage_parity_report`
  - Direct/lightweight access to `construction_source_sync_state` (via existing store/repositories and connection_setup patterns), MCP receipt/denial tables (metadata-only), unsupported claim checks, memory quality review runs, etc.
- No new write paths, no raw passthrough, no external calls. Additive only if any small receipt table were needed later (not required for this prompt).
- Exports updated in `__init__.py` only as needed for discoverability (lazy imports in routes keep the surface optional).

Existing sync-governance admin routes (Prompt 06) remain under `/admin/*` for compatibility; the new confidence read models use the documented `/api/admin/*` family to align with the /api/today etc. read-model convention.

## Frontend Implementation

- `frontend/src/lib/api.ts`: added typed (any-tolerant per project pattern) helpers: getAdmin, getAdminSourceSyncHealth, getAdminWorkflowJobHealth, getAdminEvidenceGuardrails, getAdminRetrievalAiQuality, getAdminPermissionsGovernance, getAdminDataCompleteness. Added to the exported api object.
- `frontend/src/pages/AdminDataConfidencePage.tsx`: replaced static skeleton with live data-driven implementation using TanStack Query (useQuery) against the 6 (plus root) endpoints. Renders the 6 sections as cards showing metric names + status, attention items, per-section hints, and the strong advisory language. Uses existing Badge components, links back to Today, and preserves the "secondary support surface" posture. No raw exposure, construction-facing labels, compact presentation suitable for technical-but-plain diagnostics.
- Navigation and routing (pre-existing from UI-08/09): Support nav item "Admin / Data Confidence" at `/admin`; page already registered in routes.tsx; many primary pages already link to it with phrases like "View source & sync details →" or "Open Admin / Data Confidence →". No changes required.
- UX rules honored: detailed diagnostics hidden from primary screens; compact badges + links only on ops pages; theme (dark/light/system) works; no dry-run terminology; Chat remains disabled.

## Data Flows (simplified)

```mermaid
flowchart LR
  subgraph ExistingDeterministicEvaluators
    A[automation_health + daily_brief job health]
    B[source_sync_state + procore_freshness + freshness]
    C[phase_09_gates + safety (no-raw/no-writeback proofs) + table_inventory]
    D[unsupported_claim_checks + memory_quality_review + vector/llamaindex]
    E[MCP receipts/denials + policy/audit]
    F[corpus_balance_mart + financial/doc coverage]
  end
  subgraph AnalyticsService
    G[build_admin_confidence_summary + 6 build_admin_*_health]
  end
  subgraph FastAPI
    H[/api/admin + 6 section surfaces/]
  end
  subgraph Frontend
    I[AdminDataConfidencePage: 6 live cards + metrics + attention + advisory]
  end
  A & B & C & D & E & F --"metadata-only reports, guardrail-clean"--> G
  G --"read-model contract (cards, freshness, sources, advisory, no raw)"--> H
  H --"require_admin_role (detailed); viewer gets compact badges on primary pages"--> I
  I --"links from Today/Projects/My Items (and back)"--> H
  style H fill:#ff9,stroke:#333
```

The root /api/admin returns the compact summary (already used for badges/context in other read models). The 6 surfaces return richer per-area detail for the dedicated Admin page.

## Guardrails and Contracts (enforced)

- Role: admin for detailed views (per roles_permissions.json + 03_). Non-admins see only compact badges + links on primary surfaces.
- No raw: response contract + explicit "no raw bodies, tokens, PEMs, signed URLs, prompts/responses" rules (15_SECURITY, 09_ backend rules, catalog data_caveats).
- No writeback, no external calls, no determinations (advisory/metadata only; "no legal, financial, schedule, safety or entitlement determinations").
- Local auth storage only (status/identity shown, never values).
- All surfaces include guardrails object + advisory_notes.
- "Provide compact confidence/freshness badges for operations pages and detailed diagnostics through Admin / Data Confidence." (09_).

## Verification (per 16_TESTING + 17_ + plan)

- Backend: FastAPI analytics imports cleanly (no frontend); OpenAPI generation (test_fastapi_analytics_app_shell updated with the 7 new paths); all new routes role-guarded (admin); no raw sensitive in responses; targeted analytics tests + safe `-m "not integration and not live and not manual"` (tolerate only pre-existing unrelated Phase 09 failures); ruff check/format + mypy on analytics.
- Frontend: clean install; lint (any disables only per prior pattern for api responses); tsc -b; vite build. Manual smoke: load /admin, see all 6 sections with live (or clear empty) data, metric IDs/names/status/attention/advisory visible, links to/from primary pages work, no raw, compact badges still appear on Today/Projects, Chat disabled, no new top-level nav.
- Acceptance (16_): "Admin / Data Confidence is secondary." "Admin can troubleshoot data health without dominating primary UX."
- Phase UI-13 (future) will run broader no-raw scans, no-writeback proofs, full UI route checks, and closeout evidence. This prompt delivers its own targeted verification + architecture update + traditional commit.

## Cross-References

- Planning package (all via search-only discovery for research): Prompt_11_ADMIN_CONFIDENCE.md, 14_ADMIN_DATA_CONFIDENCE.md, 09_FASTAPI_BACKEND_DESIGN.md, 10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md, 11_FRONTEND_UI_STRUCTURE.md, 12_UI_KIT..., 15_SECURITY..., 16_TESTING_VALIDATION_ACCEPTANCE.md, 17_IMPLEMENTATION_SEQUENCE.md, 03_USER_ROLES..., resources/json/{metrics_catalog.json (35 ADC + data_caveats), navigation_model.json, roles_permissions.json}, evidence_inputs/{00-readonly-audit..., 02-metrics-catalog(1).json, 03-dashboard-blueprints(1).md, 04-fastapi-analytics-endpoints(1).md, 05-readiness-and-implementation-priority(1).md}.
- Prior architecture: 176 (UI kit/nav), 177 (Today/Projects/My Items), 178 (Daily Brief external).
- Code: src/hb_assistant/construction/analytics/{api.py, service.py, __init__.py}, frontend/src/{lib/api.ts, pages/AdminDataConfidencePage.tsx, app/routes.tsx, navigation/navigationModel.ts}, tests/test_fastapi_analytics_app_shell.py (paths), and the many second-brain / store / data_quality / retrieval evaluators already present and guardrail-clean.
- Existing partial surfaces: build_admin_confidence_summary + ADC wiring, AdminDataConfidencePage skeleton + navigation entry + cross-links from primary pages (Prompts 08/09), sync-governance admin routes (Prompt 06).

This document records the Prompt 11 / UI-11 implementation. Later phases (UI-12 Settings, UI-13 closeout) will reference and extend as needed (additive, role-aware, no-raw posture preserved).

## Post-Execution Summary (per query)

- Architecture documentation updated (`docs/architecture/179-fastapi-admin-data-confidence.md`).
- Verification suite run (Python analytics gate + targeted + safe subset; frontend lint/tsc/build; manual smoke of the 6 sections + role + no-raw + links).
- Traditional commit prepared with appropriate manifest title + "Prompt 11 / UI-11" description.
- Only the commit summary and description are output as the final result.