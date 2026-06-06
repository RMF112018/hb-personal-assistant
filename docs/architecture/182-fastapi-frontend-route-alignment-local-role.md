# FastAPI Frontend Route Alignment And Local Role

This run aligns the Today frontend with the optional FastAPI analytics shell and
adds a local-only role selector for development testing. It does not add
production authentication, active chat, live source-system calls, or writeback.

## Today Compatibility Routes

The backend exposes read-only compatibility routes for the Today sub-sections:

- `GET /api/today/changes`
- `GET /api/today/meetings`
- `GET /api/today/action-items`
- `GET /api/today/portfolio-signals`

Each route is a thin section wrapper over the canonical `AnalyticsService`
Today model. Responses are metadata-only envelopes with `surface`, `items`,
`freshness`, `confidence_summary`, `guardrails`, `source`, `advisory_notes`, and
an `empty_state_reason_code` when the section has no local data.

## Local Dev Role Header

The frontend API client sends `X-HB-UI-Role` on every API request. The role is
read from `localStorage["hb-ui-role"]`; invalid values fall back to the local
default. The default role is `VITE_HB_UI_ROLE || "operator"` so Daily Brief
configuration can be tested locally while Admin screens still require manually
switching to Admin.

The app shell includes a compact selector labeled:

`Local dev role — not production auth`

Allowed local dev roles are `viewer`, `operator`, and `admin`. This selector is
only a development convenience. Backend role dependencies and route guards are
unchanged.

## Guardrails

Chat remains disabled and active chat routes remain absent. The compatibility
routes do not call Microsoft Graph, Procore live APIs, Typer commands, or any
source-system writeback path. Responses must not serialize raw email/document
content, raw prompts/responses, auth tokens, client secrets, signed URLs, or
download URLs.
