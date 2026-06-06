# 171 — FastAPI Auth Onboarding Surfaces (Prompt 03)

**Objective:** add first-run authentication onboarding/status surfaces for the
optional analytics UI shell. The surfaces cover Microsoft Graph delegated device
login and Procore OAuth OOB login while preserving local-first token storage and
redacted responses.

## Routes

The FastAPI shell now exposes:

- `GET /onboarding/auth/status`
- `GET /auth/graph/status`
- `POST /auth/graph/device-login/start`
- `POST /auth/graph/device-login/complete`
- `GET /auth/procore/status`
- `POST /auth/procore/oauth/start`
- `POST /auth/procore/oauth/exchange`

Status routes are available to `viewer`, `operator`, and `admin`. Auth start,
complete, and exchange routes require `operator` or `admin`; `viewer` receives
403. No route calls Typer/CLI commands.

## Graph Flow

Graph uses the existing delegated MSAL provider and token-cache manager. Start
creates an MSAL device flow and returns only onboarding instructions
(`flow_id`, verification URI, user code, interval/expiry). Complete consumes the
opaque in-memory `flow_id`, polls MSAL, and saves the delegated cache locally
through the existing cache manager.

The service does not call Graph data APIs. It never returns access tokens, MSAL
cache bodies, raw Graph responses, or auth request bodies.

## Procore Flow

Procore uses the existing `ProcoreOAuthClient` and local OAuth cache writer.
Start returns the OOB authorization URL. Exchange accepts the pasted
authorization code, performs the token exchange through the OAuth client, and
writes the existing local Procore token cache.

The route response reports cached-token booleans and expiry metadata only. It
does not return access tokens, refresh tokens, client secrets, OAuth request
bodies, raw OAuth responses, or Procore data API results.

## Guardrails

All onboarding outputs are metadata-only and local-cache-focused. They do not
perform source-system writeback, Procore live data calls, Graph data calls, CLI
shell-outs, active chat, or frontend serving. Token values and secret material
must remain confined to the existing local auth cache mechanisms.
