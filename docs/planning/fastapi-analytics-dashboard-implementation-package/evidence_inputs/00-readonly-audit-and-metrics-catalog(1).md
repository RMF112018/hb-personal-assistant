# Read-Only Audit And Metrics Catalog

Generated: `2026-06-06T08:51:37.822207+00:00`

This evidence package supports `docs/planning/ui-analytics-metrics-exploration/` for a future FastAPI/UI analytics dashboard. The revised catalog is construction-operations-first: the main product should feel like a GC operations command center for executives, PXs, PMs, superintendents, commercial leaders, and financial leaders. Admin / Data Confidence metrics remain required, but they support trust, governance, and troubleshooting rather than dominating the primary dashboard.

## Revised Catalog Summary

- Total proposed metrics: `135`
- Construction Operations metrics: `90`
- Admin / Data Confidence metrics: `35`
- Hybrid metrics: `10`
- Previous seed catalog: `56` metrics, now superseded for dashboard planning by the revised two-layer catalog.

| Layer | Metric count |
| --- | --- |
| construction_operations | 90 |
| admin_data_confidence | 35 |
| hybrid | 10 |

## Dashboard Area Coverage

| Dashboard area | Metric count |
| --- | --- |
| Executive Portfolio | 9 |
| Project Health | 8 |
| Cost & Financial Exposure | 10 |
| Change Management | 8 |
| Schedule & Procurement Risk | 8 |
| RFIs / Submittals / Design Decisions | 8 |
| Field Operations / Quality / Safety | 8 |
| Document Control | 7 |
| Correspondence & Decision Velocity | 7 |
| Meetings / Action Items | 7 |
| Subcontractor / Vendor Performance | 7 |
| Billing / Cash / Retention | 7 |
| Closeout Readiness | 6 |
| Source / Sync Health | 7 |
| Workflow / Job Health | 5 |
| Evidence / Guardrail Health | 6 |
| Retrieval / AI Quality | 7 |
| Permissions / Governance | 5 |
| Data Completeness / Coverage | 5 |

## Product Direction

Construction Operations metrics are the headline KPI layer. Every construction-operations metric is written to pass an executive usefulness test: a PM, PX, superintendent, commercial leader, or company executive can plausibly act on it. Source confidence, sync freshness, endpoint coverage, evidence status, and retrieval readiness are supporting context for those metrics unless they are placed in Admin / Data Confidence.

## Guardrails

Metrics may identify signals, exposure, aging, attention items, or review-required conditions. They must not make legal, claims, entitlement, payment, schedule-delay, safety, or financial determinations. Financial metrics are readiness/exposure indicators only. Schedule metrics are signals only. Correspondence metrics are decision-velocity and review aids only.

## Source Posture

This revision did not query or write the operator DB. It reuses the earlier read-only package inventory and schema context. No production code, migrations, runtime config, external systems, Obsidian vault, auth cache, or operator DB were modified.
