# Proposed FastAPI Analytics Endpoints

All endpoints are proposed read-only surfaces. No implementation code is included in this evidence package.

## Construction Operations Endpoints

| Endpoint family | Primary dashboard areas | Notes |
| --- | --- | --- |
| `GET /analytics/operations/executive-portfolio` | Executive Portfolio | Attention items, portfolio exposure, decision aging, cash and closeout signals. |
| `GET /analytics/operations/projects/{project_key}/health` | Project Health | Open action signals, recent changes, relationship gaps, confidence badges. |
| `GET /analytics/operations/cost-exposure` | Cost & Financial Exposure | Advisory exposure/readiness signals only; never forecasts or approvals. |
| `GET /analytics/operations/change-management` | Change Management | Change aging, approval aging, RFQ follow-through, documentation completeness. |
| `GET /analytics/operations/schedule-procurement` | Schedule & Procurement Risk | Schedule/procurement signals only; never delay determinations. |
| `GET /analytics/operations/decisions` | RFIs / Submittals / Design Decisions | RFI/submittal/design-team decision velocity and aging. |
| `GET /analytics/operations/field` | Field Operations / Quality / Safety | Field issue and review-required quality/safety signals only. |
| `GET /analytics/operations/documents` | Document Control | Document-control metadata, review queues, relationship candidates. |
| `GET /analytics/operations/correspondence` | Correspondence & Decision Velocity | Metadata and decision candidates; no claim positions. |
| `GET /analytics/operations/meetings-actions` | Meetings / Action Items | Meeting prep, action aging, follow-through. |
| `GET /analytics/operations/vendors` | Subcontractor / Vendor Performance | Vendor action load, compliance, invoice, attribution confidence. |
| `GET /analytics/operations/billing-cash` | Billing / Cash / Retention | Billing/payment/retainage signals only. |
| `GET /analytics/operations/closeout` | Closeout Readiness | Closeout blockers and attention items. |

## Admin / Data Confidence Endpoints

| Endpoint family | Primary dashboard areas | Notes |
| --- | --- | --- |
| `GET /analytics/admin/source-sync-health` | Source / Sync Health | Source coverage, sync freshness, blocked/review-routed items. |
| `GET /analytics/admin/workflow-job-health` | Workflow / Job Health | Runs, steps, retries, daily brief receipts. |
| `GET /analytics/admin/evidence-guardrails` | Evidence / Guardrail Health | Data-quality gates, no-writeback/no-raw proof status. |
| `GET /analytics/admin/retrieval-ai-quality` | Retrieval / AI Quality | Retrieval/vector/LlamaIndex/embedding/eval readiness. |
| `GET /analytics/admin/permissions-governance` | Permissions / Governance | MCP receipts/denials, permission posture, prohibited metrics. |
| `GET /analytics/admin/data-completeness` | Data Completeness / Coverage | Table/source/domain coverage and completeness snapshots. |

## Response Requirements

Every response should include metric IDs, source table/read-model names, freshness/confidence context, guardrail caveats, and source-linked drilldown references. Raw bodies, raw document text, raw prompts/responses, auth material, tokens, signed URLs, and secret-like values must not be serialized.
