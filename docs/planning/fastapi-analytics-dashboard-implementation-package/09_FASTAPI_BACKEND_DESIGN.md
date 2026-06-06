# FastAPI Backend Design

## Purpose

FastAPI is the read-only interface layer for the CM-first analytics dashboard, onboarding/connection setup, user/admin settings, Daily Brief file presentation, and Admin / Data Confidence support surfaces.

The backend must support the simplified navigation model:

- Today
- Projects
- My Items
- Admin / Data Confidence
- Settings

It must not expose top-level API concepts that force the frontend to behave like a CLI wrapper. Internal services may still map to detailed construction domains, but user-facing route families should support the simplified UI hierarchy.

---

## Suggested Module Layout

```text
src/hb_assistant/ui_api/
  app.py
  deps.py
  models/
    roles.py
    settings.py
    connections.py
    analytics.py
    daily_brief.py
    jobs.py
    navigation.py
  routers/
    health.py
    onboarding.py
    auth_status.py
    connections.py
    today.py
    projects.py
    my_items.py
    admin_confidence.py
    settings.py
    daily_brief.py
    review.py
    chat_stub.py
  services/
    auth_status_service.py
    connection_service.py
    project_service.py
    today_service.py
    projects_dashboard_service.py
    my_items_service.py
    daily_brief_file_service.py
    sync_policy_service.py
    settings_service.py
    admin_confidence_service.py
    review_service.py
  read_models/
    today.py
    portfolio.py
    project_overview.py
    project_meetings.py
    project_field_operations.py
    project_cost_time.py
    my_items.py
    admin_confidence.py
```

Detailed domain read models may still exist internally:

```text
read_models/
  cost_exposure.py
  change_management.py
  schedule_procurement.py
  correspondence.py
  documents.py
  meetings.py
  vendors.py
  billing_cash.py
  closeout.py
```

But the frontend should consume them through Today, Projects, My Items, or Admin endpoints.

---

## Primary Route Families

### System and onboarding

- `GET /api/health`
- `GET /api/navigation`
- `GET /api/onboarding/status`
- `POST /api/onboarding/graph/start-device-login`
- `POST /api/onboarding/procore/start-login`
- `GET /api/auth-status/graph`
- `GET /api/auth-status/procore`

### Data connections

- `GET /api/connections`
- `POST /api/connections/sharepoint/resolve-url`
- `POST /api/connections/sharepoint/add`
- `POST /api/connections/procore/resolve-project-url`
- `POST /api/connections/procore/add-project`
- `GET /api/connections/onedrive/folders`
- `POST /api/connections/onedrive/scope`
- `POST /api/connections/outlook/scope`
- `POST /api/connections/calendar/scope`

Outlook and Calendar “project matching only” must be available but not default.

### Today

- `GET /api/today`
- `GET /api/today/important`
- `GET /api/today/changes`
- `GET /api/today/meetings`
- `GET /api/today/action-items`
- `GET /api/today/portfolio-signals`
- `GET /api/today/daily-brief`

### Projects

- `GET /api/projects`
- `GET /api/projects/portfolio`
- `GET /api/projects/all/overview`
- `GET /api/projects/all/meetings`
- `GET /api/projects/all/field-operations`
- `GET /api/projects/all/cost-time`
- `GET /api/projects/{project_key}/overview`
- `GET /api/projects/{project_key}/meetings`
- `GET /api/projects/{project_key}/field-operations`
- `GET /api/projects/{project_key}/cost-time`
- `GET /api/projects/{project_key}/keywords`
- `POST /api/projects/{project_key}/keywords`
- `PATCH /api/projects/{project_key}/keywords/{keyword_id}`
- `DELETE /api/projects/{project_key}/keywords/{keyword_id}`

### My Items

- `GET /api/my-items`
- `GET /api/my-items/action-items`
- `GET /api/my-items/meetings`
- `GET /api/my-items/correspondence`
- `GET /api/my-items/files`
- `GET /api/my-items/followed-projects`

### Daily Brief

- `GET /api/daily-brief/status`
- `GET /api/daily-brief/latest`
- `POST /api/daily-brief/configure`
- `POST /api/daily-brief/generate-setup-instructions`
- `POST /api/daily-brief/validate-output-folder`
- `POST /api/daily-brief/detect-latest`

The app presents externally generated Markdown. It does not generate the Daily Brief through in-app chat.

### Admin / Data Confidence

- `GET /api/admin`
- `GET /api/admin/source-sync-health`
- `GET /api/admin/workflow-job-health`
- `GET /api/admin/evidence-guardrails`
- `GET /api/admin/retrieval-ai-quality`
- `GET /api/admin/permissions-governance`
- `GET /api/admin/data-completeness`

### Settings

- `GET /api/settings`
- `PATCH /api/settings/user`
- `PATCH /api/settings/admin`
- `POST /api/settings/auth/graph/revoke-local`
- `POST /api/settings/auth/procore/revoke-local`

### Chat stub

- `GET /api/chat/status`

This endpoint must return disabled/future-only status. No active chat UI or route is allowed.

---

## Backend Rules

- No raw SQL endpoint.
- No direct Graph/Procore passthrough endpoint.
- No source-system writeback.
- No exposed dry-run/apply/execute terminology in normal construction-user routes.
- Use Pydantic request/response models.
- Use role/policy dependencies.
- Serialize freshness/confidence context without exposing raw content.
- Keep all token values, raw bodies, signed URLs, and secrets out of responses.
- Provide compact confidence/freshness badges for operations pages and detailed diagnostics through Admin / Data Confidence.
