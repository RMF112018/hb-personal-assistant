# P03 — Procore Safe Status and Auth Bridge

Expose Procore status and safe OAuth/auth actions.

Inspect existing `hb-assistant procore` CLI/services for auth status, auth refresh, mapping validate, live-read gates, keychain/env token handling, project mapping, source-refresh integration, and no-writeback rules.

Add/adapt:
- `GET /api/sources/procore/status`;
- `POST /api/sources/procore/auth/start` if supported;
- `GET /api/sources/procore/auth/callback` if supported;
- `GET /api/sources/procore/auth/status` if supported;
- `POST /api/sources/procore/auth/refresh` if safe refresh exists.

Status and auth refresh must not call project list/sync/live content APIs.

Tests must prove metadata-only response, no live Procore client calls, no tokens/secrets/cache paths, and correct missing-config/missing-mapping states.
