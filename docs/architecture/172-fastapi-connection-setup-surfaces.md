# FastAPI Connection Setup Surfaces

Prompt 04 adds connection setup routes to the optional analytics FastAPI shell.
The flow is preview first, explicit local save second, and admin approval before
any first sync can be scheduled. The routes do not call Graph, Procore live data
APIs, Typer commands, frontend assets, or external writeback paths.

## Route Inventory

- `POST /connections/preview` classifies a submitted Procore, SharePoint,
  OneDrive, Outlook, or Calendar setup request and returns metadata-only setup
  guidance. It permits `viewer`, `operator`, and `admin`.
- `POST /connections/save` re-runs classification and persists an approved
  local setup record. It requires `operator` or `admin`.
- `POST /admin/connections/{connection_id}/approve-first-sync` marks a saved
  connection as approved for a later first sync. It requires `admin`.
- `POST /admin/projects/{project_key}/sync-schedule` records local schedule
  intent when saved project sources exist. It requires `admin`.

## Classification Rules

Procore homepage/project URLs are parsed locally for a numeric project ID and
matched to the existing source registry when a local project carries the same
`procore_project_id`. Unsupported URLs fail closed with reason codes.

SharePoint URLs are classified as a site, project-drive folder/library scope, or
site page. The service stores only local setup metadata and strips URL query and
fragment components from persisted SharePoint web URLs.

OneDrive setup must be explicit: selected folders, explicit all-folders approval,
or excluded. Implicit root-wide OneDrive setup is rejected. Selected-folder setup
requires a folder item identifier in the request or URL query.

Outlook and Calendar setup exposes read-only options from existing local policy
shapes: metadata-only mail folders and primary-calendar defaults. Event bodies,
join URLs, mailbox mutation, and full email body persistence stay disabled.

## Local Persistence

Prompt 04 intentionally avoids a migration. Saved file-source setup reuses
`construction_source_locations` and `construction_source_sync_state` with
`sync_status='pending_admin_approval'`. Saved Outlook and Calendar setup reuses
`email_source_locations`, `email_sync_state`, `calendar_source_locations`, and
`calendar_sync_state`. Saved Procore setup reuses `construction_project_identity`
for the local project-to-Procore ID association.

Admin approval updates local sync state to `approved_first_sync_not_started`.
No route starts a crawler, delta sync, live Procore pull, Graph request, or
mail/calendar indexing run.

## Guardrails

Responses never include bearer tokens, refresh tokens, auth cache bodies, client
secrets, raw Graph or Procore responses, raw prompts/responses, signed URLs, or
download URLs. The service returns URL fingerprints and setup metadata instead
of source-system response bodies. Active chat remains disabled and no frontend
surface is added in this prompt.
