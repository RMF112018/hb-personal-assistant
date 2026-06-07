# P02 — Microsoft Graph Safe Status and Auth Bridge

Expose Graph/Microsoft 365 status and safe auth actions.

Inspect existing `hb-assistant graph` CLI/services for mail/calendar/files status, token cache, scopes, app-support root, and no-writeback guards.

Add/adapt:
- `GET /api/sources/graph/status`;
- `POST /api/sources/graph/auth/start` if supported;
- `GET /api/sources/graph/auth/status` if polling is supported;
- `POST /api/sources/graph/auth/refresh` if safe refresh exists.

Status and auth refresh must not read mail/calendar/files or trigger sync.

Tests must prove metadata-only response, no content API calls, no tokens/cache paths, and correct stale/missing-scope states.
