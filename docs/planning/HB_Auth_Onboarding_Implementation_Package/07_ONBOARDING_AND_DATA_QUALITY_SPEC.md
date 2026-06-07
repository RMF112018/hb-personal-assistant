# Onboarding and Data Quality Specification

## First-Time Session Handling

A fully unauthenticated session must land on `/get-started`.

A session is fully unauthenticated when:

- there is no prior Graph auth cache or usable account metadata;
- there is no prior Procore token cache or usable account metadata;
- there are no saved source connections capable of eventual approved sync;
- the app cannot present meaningful existing data.

## Returning Session Handling

A returning user should not be forced through Get Started solely because auth is stale.

Startup logic:

```text
Call readiness endpoint
  -> backend detects prior auth/setup
  -> backend attempts silent refresh for stale refreshable auth
  -> if refresh succeeds: main app allowed
  -> if refresh fails: main app allowed if usable prior data exists, with source-specific reauth prompt
  -> if no usable prior data exists: Get Started / Reconnect mode
```

## Automated Refresh Requirements

Graph:

- Use MSAL cache/account discovery.
- Attempt silent token acquisition before prompting reauth.
- Return safe status only.

Procore:

- Use refresh token path in local token provider/cache.
- Attempt refresh before prompting reauth.
- Return safe status only.

## Reauth Prompting

Reauth prompts should be source-specific:

- `Microsoft 365 needs re-authentication.`
- `Procore needs re-authentication.`

Do not display generic system failure unless both sources are unavailable and no usable data exists.

## Non-Admin Data Quality

Non-admin users see only:

- `Data Quality` label.
- status dot.
- latest update time on hover.
- one plain-language status message.

They do not see:

- approval queue details.
- source-specific sync failure tables.
- diagnostic JSON.
- token/cache/auth internals.
- raw source confidence calculations.

## Admin Data Quality

Admins may see:

- source-by-source status.
- last successful sync per source.
- next scheduled sync.
- stale source list.
- failed sync reason.
- pending approval queue.
- disabled action reasons.
- account reauth requirements.

Even admin views must not expose tokens, secrets, local cache paths, raw source payloads, raw content, or external signed/download URLs.

## Data Quality Scoring Guidance

Initial logic may be deterministic and conservative.

Green / good:

- At least one approved source has successful sync inside configured freshness window.
- Required auth is valid or refreshed.
- No blocking sync failures for active approved sources.

Yellow / degraded:

- Prior data exists, but one or more active sources are stale.
- Auth was refreshed recently but source sync has not yet run.
- Connection is saved but pending admin approval.
- Partial source availability.

Red / poor:

- No trusted source data exists.
- Required auth failed and no prior usable data exists.
- Last governed sync failed for all active approved sources.
- Source setup is incomplete.

Unknown:

- App cannot determine quality because setup has not started or metadata is missing.
- Non-admin UI may display unknown as yellow if prior setup exists, red if no trusted data exists.
