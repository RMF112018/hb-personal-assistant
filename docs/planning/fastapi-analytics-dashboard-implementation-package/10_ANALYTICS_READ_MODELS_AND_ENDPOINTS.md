# Analytics Read Models and Endpoints

## Endpoint Design Principle

The API should support the simplified UI hierarchy:

- Today
- Projects
- My Items
- Admin / Data Confidence
- Settings

Detailed construction domains are still implemented internally, but they should not force broad top-level frontend navigation. Instead, they are composed into dashboard read models.

---

## Dashboard-Level Read Models

### Today read model

Endpoint family:

- `GET /api/today`
- `GET /api/today/important`
- `GET /api/today/changes`
- `GET /api/today/meetings`
- `GET /api/today/action-items`
- `GET /api/today/portfolio-signals`
- `GET /api/today/daily-brief`

Combines:

- portfolio attention items;
- all-project recent changes;
- meeting prep readiness;
- Daily Brief status/presentation;
- action items;
- correspondence worth reviewing;
- document changes;
- cost/change/schedule/field/closeout/billing signals.

### Projects read models

Endpoint family:

- `GET /api/projects/portfolio`
- `GET /api/projects/all/overview`
- `GET /api/projects/all/meetings`
- `GET /api/projects/all/field-operations`
- `GET /api/projects/all/cost-time`
- `GET /api/projects/{project_key}/overview`
- `GET /api/projects/{project_key}/meetings`
- `GET /api/projects/{project_key}/field-operations`
- `GET /api/projects/{project_key}/cost-time`

Projects must support both:

- aggregated All Projects dashboards;
- individual project dashboards.

### My Items read model

Endpoint family:

- `GET /api/my-items`
- `GET /api/my-items/action-items`
- `GET /api/my-items/meetings`
- `GET /api/my-items/correspondence`
- `GET /api/my-items/files`
- `GET /api/my-items/followed-projects`

Combines user-specific Outlook, calendar, OneDrive, open action items, followed projects, review-required items, and locally reviewed/unreviewed states.

### Admin / Data Confidence read models

Endpoint family:

- `GET /api/admin/source-sync-health`
- `GET /api/admin/workflow-job-health`
- `GET /api/admin/evidence-guardrails`
- `GET /api/admin/retrieval-ai-quality`
- `GET /api/admin/permissions-governance`
- `GET /api/admin/data-completeness`

These are support surfaces, not the primary user experience.

---

## Domain Composition

Domain-specific metrics should be composed into the dashboard models as follows:

| Domain | Primary location |
| --- | --- |
| Executive Portfolio | Today, Projects Portfolio |
| Project Health | Projects Overview |
| Cost & Financial Exposure | Projects Cost & Time, Today |
| Change Management | Projects Cost & Time, Today |
| Schedule & Procurement Risk | Projects Cost & Time, Today |
| RFIs / Submittals / Design Decisions | Projects Overview, Projects Cost & Time |
| Field Operations / Quality / Safety | Projects Field Operations |
| Document Control | Today, Projects Overview, My Items |
| Correspondence & Decision Velocity | Today, Projects Meetings, My Items |
| Meetings / Action Items | Today, Projects Meetings, My Items |
| Subcontractor / Vendor Performance | Projects Overview, Projects Cost & Time, Today |
| Billing / Cash / Retention | Projects Cost & Time, Today |
| Closeout Readiness | Projects Field Operations, Projects Overview, Today |
| Source / Sync Health | Admin / Data Confidence |
| Workflow / Job Health | Admin / Data Confidence |
| Evidence / Guardrail Health | Admin / Data Confidence |
| Retrieval / AI Quality | Admin / Data Confidence |
| Permissions / Governance | Admin / Data Confidence |
| Data Completeness / Coverage | Admin / Data Confidence |

---

## Response Contract

Every dashboard response should include:

- page/dashboard ID;
- generated timestamp;
- freshness/confidence summary;
- metric cards;
- attention items;
- sections;
- drilldown references;
- source/read-model names;
- advisory language where applicable;
- empty/stale/error states.

Every metric item should include:

- metric ID;
- user-facing name;
- value;
- unit/format;
- freshness context;
- confidence/context badge;
- source/read-model names;
- advisory language where applicable;
- drilldown target.

No raw bodies, raw document text, raw prompts/responses, auth material, tokens, signed URLs, or secret-like values may be serialized.

---

## MVP Metric Priority

Use `evidence_inputs/05-readiness-and-implementation-priority(1).md` for Top 20 and role-specific priority lists, but compose the MVP into:

1. Today dashboard;
2. Projects Portfolio / All Projects;
3. Individual Project Overview;
4. My Items;
5. Admin / Data Confidence.
