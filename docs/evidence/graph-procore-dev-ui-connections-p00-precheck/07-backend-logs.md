# P00 — 07 Backend Logs (correlated)

Source: `~/Library/Application Support/HB Personal Assistant (Dev)/logs/launcher/dev-backend.log`
Captured: 2026-06-07 · Backend: uvicorn factory on `127.0.0.1:8000`

## Health

No `5xx` and **no tracebacks/exceptions** in the backend log — the FastAPI shell is healthy. All
observed non-2xx are deliberate, fail-closed `403`/`404` (see below).

## Recurring `403 Forbidden` — `/api/settings/admin-sync`

The log shows this 403 repeated across many client ports (both the launcher-opened default-role browser
session and direct probes):

```
INFO: 127.0.0.1:61055 - "GET /api/settings/admin-sync HTTP/1.1" 403 Forbidden
INFO: 127.0.0.1:61073 - "GET /api/settings/admin-sync HTTP/1.1" 403 Forbidden
…(repeats)…
INFO: 127.0.0.1:62011 - "GET /api/settings/admin-sync HTTP/1.1" 403 Forbidden
```

Cross-checked by explicit role probes:

| Role header | `/api/settings/admin-sync` |
|---|---|
| `viewer` | 403 |
| `operator` | 403 |
| *(no header → default)* | 403 |
| `admin` | 200 |

The backend guard is **correct and fail-closed**. The cause of the repeated 403s is the **frontend**:
`frontend/src/components/settings/AdminFirstSyncApprovalPanel.tsx:22` calls `getAdminPendingApprovals()`
**unconditionally on mount** with no client-side role gate, so any non-admin (default) user fires the
admin-only endpoint and receives 403.

## `404 Not Found` — aggregate source-status endpoints (probed)

```
INFO: 127.0.0.1:61768 - "GET /api/environment HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:61771 - "GET /api/sources/status HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:61675 - "GET /api/health HTTP/1.1" 404 Not Found   (health is at /health, not /api/health)
```

These confirm the GPC-P0-001 aggregate source-status surface is not implemented.

## Healthy 2xx (Settings/Connections data plane)

The admin-role browser session (Playwright) and curl probes show the data plane returns 200 for the
real Settings/Connections endpoints:

```
GET /api/settings/accounts                200 OK
GET /api/settings/connections/projects    200 OK
GET /api/settings/daily-brief             200 OK
GET /api/settings/data-quality/summary    200 OK
GET /api/settings/data-quality/detail     200 OK
GET /api/settings/preferences             200 OK
GET /api/settings/keywords                200 OK
GET /api/my-items                         200 OK
GET /api/projects/portfolio               200 OK
```
