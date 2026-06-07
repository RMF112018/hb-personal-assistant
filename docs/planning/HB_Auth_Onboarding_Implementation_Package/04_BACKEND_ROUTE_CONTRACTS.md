# Backend Route Contracts

All route responses must be safe to serialize to the frontend.

## Shared Enums

```text
AuthSource = graph | procore
AuthStatus = never_connected | connected_valid | connected_refreshing | connected_stale_refreshable | connected_stale_reauth_required | connected_error | disconnected_by_user
OnboardingState = first_time | ready | degraded | reauth_required | blocked
DataQualityStatus = good | degraded | poor | unknown
ApprovalStatus = not_requested | pending | approved | rejected | not_required
```

## GET /api/onboarding/readiness

Purpose: startup decision route for `/get-started` vs app shell vs re-auth prompt.

Behavior:

- May perform safe automated refresh attempts for stale cached auth.
- Must not start sync.
- Must not call live external APIs unless the refresh operation requires token endpoint communication.
- Must not expose tokens, refresh tokens, claims beyond safe account metadata, file paths, or debug payloads.

Response:

```json
{
  "onboarding_state": "first_time",
  "has_prior_setup": false,
  "main_app_allowed": false,
  "get_started_required": true,
  "reauth_required": [],
  "required_actions": [
    {
      "source": "graph",
      "status": "never_connected",
      "message": "Connect Microsoft 365 to begin setup."
    }
  ],
  "data_quality": {
    "status": "unknown",
    "label": "Data Quality",
    "last_updated_at": null,
    "message": "No approved source data has been collected yet."
  }
}
```

## GET /api/settings/connections/accounts

Purpose: safe account connection summary for Settings.

Response:

```json
{
  "graph": {
    "source": "graph",
    "status": "connected_valid",
    "display_name": "Bobby Fetting",
    "account_hint": "bfetting@...",
    "tenant_hint": "...",
    "scopes": ["User.Read", "Mail.Read", "Calendars.Read", "Files.Read.All", "offline_access"],
    "needs_reauth": false,
    "last_verified_at": "2026-06-07T20:00:00-04:00",
    "message": "Microsoft 365 is connected."
  },
  "procore": {
    "source": "procore",
    "status": "never_connected",
    "account_hint": null,
    "company_hint": null,
    "needs_reauth": false,
    "last_verified_at": null,
    "message": "Procore is not connected."
  }
}
```

## POST /api/settings/connections/auth/refresh

Purpose: user/session-triggered automated refresh attempt for all stale-but-refreshable sources.

Request:

```json
{
  "sources": ["graph", "procore"]
}
```

Response:

```json
{
  "results": [
    {
      "source": "graph",
      "before": "connected_stale_refreshable",
      "after": "connected_valid",
      "reauth_required": false,
      "message": "Microsoft 365 authentication refreshed."
    }
  ]
}
```

## Microsoft Graph Auth Routes

### POST /api/settings/connections/graph/auth/start

Starts MSAL device-code flow.

Response:

```json
{
  "flow_id": "opaque-local-session-id",
  "verification_uri": "https://microsoft.com/devicelogin",
  "user_code": "ABCD-EFGH",
  "expires_at": "2026-06-07T20:15:00-04:00",
  "interval_seconds": 5,
  "message": "Sign in to Microsoft 365 using the displayed code. Connecting does not start sync."
}
```

### GET /api/settings/connections/graph/auth/status?flow_id=...

Polls or completes pending device flow.

Response states:

```json
{
  "flow_id": "opaque-local-session-id",
  "status": "pending | complete | expired | failed | cancelled",
  "account": {
    "display_name": "Bobby Fetting",
    "account_hint": "bfetting@...",
    "tenant_hint": "...",
    "scopes": ["User.Read", "Mail.Read", "Calendars.Read", "Files.Read.All", "offline_access"]
  },
  "message": "Microsoft 365 is connected."
}
```

### POST /api/settings/connections/graph/disconnect-local

Clears local Graph token cache/account metadata only. Does not revoke tenant permissions unless an explicit future revocation feature is implemented.

## Procore Auth Routes

### POST /api/settings/connections/procore/auth/start

Generates OAuth authorization URL and server-side state.

Response:

```json
{
  "flow_id": "opaque-local-session-id",
  "authorization_url": "https://...",
  "expires_at": "2026-06-07T20:15:00-04:00",
  "callback_mode": "localhost",
  "manual_code_fallback_available": true,
  "message": "Open Procore to authorize. Connecting does not start sync."
}
```

### GET /api/settings/connections/procore/auth/callback?code=...&state=...

Backend callback route.

Behavior:

- Validate `state`.
- Exchange code server-side.
- Store token only in secure local cache.
- Return minimal browser-safe HTML: `Procore connected. You may return to the app.`

### GET /api/settings/connections/procore/auth/status?flow_id=...

Polls Procore auth completion.

Response:

```json
{
  "flow_id": "opaque-local-session-id",
  "status": "pending | complete | expired | failed | cancelled",
  "account": {
    "account_hint": "user@company.com",
    "company_hint": "Hedrick Brothers Construction"
  },
  "message": "Procore is connected."
}
```

### POST /api/settings/connections/procore/auth/exchange-code

Manual fallback only. Accepts authorization code pasted by user. Must be hidden unless callback flow fails or is unavailable.

### POST /api/settings/connections/procore/disconnect-local

Clears local Procore token cache/account metadata only.

## Project Connection Routes

### POST /api/settings/connections/projects/preview

Request:

```json
{
  "project_id": "local-project-id",
  "source_type": "procore | sharepoint | onedrive | outlook | calendar",
  "url": "https://...",
  "options": {
    "project_matching_only": false
  }
}
```

Response:

```json
{
  "preview_id": "opaque-preview-id",
  "source_type": "procore",
  "parsed": {
    "company_id": "redacted-safe-id-or-null",
    "project_id": "redacted-safe-id-or-null",
    "display_name": "Project Name"
  },
  "eligible_to_save": true,
  "warnings": [],
  "message": "Preview complete. No sync has started."
}
```

### POST /api/settings/connections/projects/save

Persists local connection metadata and queues or marks first-sync approval requirement.

Response:

```json
{
  "connection_id": "local-connection-id",
  "source_type": "procore",
  "approval_status": "pending",
  "sync_allowed": false,
  "message": "Connection saved. First live sync requires admin approval."
}
```

### GET /api/settings/connections/projects

Lists saved connections with safe statuses.

## Data Quality Routes

### GET /api/settings/data-quality/summary

Safe for all roles.

```json
{
  "status": "good | degraded | poor | unknown",
  "label": "Data Quality",
  "last_updated_at": "2026-06-07T20:00:00-04:00",
  "message": "Sources are current.",
  "admin_detail_available": true
}
```

### GET /api/settings/data-quality/detail

Admin-only. May include source-by-source freshness and failure summaries but still no raw content, tokens, secrets, download URLs, signed URLs, or raw debug dumps.
