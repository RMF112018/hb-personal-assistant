# Target Architecture

## System Boundaries

The frontend must interact with a safe backend façade. It should not call low-level auth utilities or receive raw auth artifacts.

```text
Frontend UI
  -> frontend/src/lib/api.ts typed helpers
  -> /api/onboarding/readiness
  -> /api/settings/connections/*
  -> backend auth/session/status services
  -> local token cache / keychain / existing provider utilities
```

## Primary Route Families

- `/api/onboarding/readiness`
- `/api/settings/connections/accounts`
- `/api/settings/connections/graph/*`
- `/api/settings/connections/procore/*`
- `/api/settings/connections/projects/*`
- `/api/settings/connections/admin/*`
- `/api/settings/data-quality/summary`
- `/api/settings/data-quality/detail` admin-only

## Auth State Model

Use a source-level state model that separates first-time setup, valid auth, stale auth, refreshable auth, failed refresh, and explicit disconnect.

```text
never_connected
connected_valid
connected_refreshing
connected_stale_refreshable
connected_stale_reauth_required
connected_error
disconnected_by_user
```

## Onboarding State Model

```text
first_time
ready
degraded
reauth_required
blocked
```

Rules:

- `first_time`: no prior authenticated account and no usable setup state.
- `ready`: auth and at least one approved data source are usable or the product can operate normally.
- `degraded`: prior data exists but one or more source paths are stale, pending, or partially unavailable.
- `reauth_required`: automated refresh failed for required auth and user action is needed.
- `blocked`: no usable data path exists and setup cannot proceed without user action.

## Microsoft Graph Decision

Use MSAL device-code flow as the primary local-first path.

Why:

- Cross-platform local app compatible.
- Avoids redirect URI and local browser callback complexity.
- Existing repo declares `msal` and has device-code primitives.
- Tokens remain in local backend-controlled cache only.

## Procore Decision

Use backend-controlled OAuth start + localhost callback as the primary path. Retain manual authorization-code fallback for environments where browser callback is unavailable.

Why:

- Better non-engineering UX than manual OOB code only.
- Keeps token exchange and token cache inside backend.
- Supports state validation and consistent Settings polling.

## Sync Governance

Setup is not sync. Auth is not sync. Preview is not sync. Save is not sync.

First live sync is available only when:

1. Account auth is valid.
2. Project/source connection is saved.
3. Source is approved by admin.
4. Sync is requested through governed command path or scheduled sync runner.
5. The source's policy permits read-only collection.

## Data Quality Surface

All users:

- sidebar footer indicator only.
- green/yellow/red dot.
- label: `Data Quality`.
- latest update timestamp and plain-language summary on hover.

Admins:

- detailed diagnostics in Settings.
- source-by-source freshness.
- auth state.
- approval state.
- last failure reason.
- next scheduled sync.
- disabled-action reasons.
