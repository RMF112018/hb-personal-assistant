# API Contract and Security Standard

## Browser-safe response rules

Never return these to the frontend:

- access tokens;
- refresh tokens;
- client secrets;
- token cache paths;
- raw email body;
- raw calendar body;
- join URLs;
- raw Procore payloads;
- stack traces;
- unredacted filesystem paths.

## Proposed endpoint semantics

| Method | Endpoint | Purpose | Live reads | Writes |
|---|---|---|---:|---:|
| GET | `/api/environment` | environment/source mode | no | no |
| GET | `/api/sources/status` | aggregate source status | no | no |
| GET | `/api/sources/graph/status` | Graph auth/cache/scopes/local sync metadata | no | no |
| POST | `/api/sources/graph/auth/start` | backend-controlled Graph auth start | no | auth transaction only |
| GET | `/api/sources/graph/auth/status` | poll auth result | no | no |
| POST | `/api/sources/graph/auth/refresh` | token refresh only | no | token cache only |
| GET | `/api/sources/procore/status` | Procore auth/config/mapping/local sync metadata | no | no |
| POST | `/api/sources/procore/auth/start` | backend-controlled Procore OAuth start | no | auth transaction only |
| GET | `/api/sources/procore/auth/callback` | Procore OAuth callback | no | token cache only |
| GET | `/api/sources/procore/auth/status` | poll auth result | no | no |
| POST | `/api/sources/procore/auth/refresh` | token refresh only | no | token cache only |
| POST | `/api/sources/refresh/dry-run` | preview refresh | no | no |
| POST | `/api/sources/refresh/local` | Dev local/mock refresh | no | local/dev data only |
| POST | `/api/sources/refresh/live` | gated live refresh | only if gates pass | orchestrator-controlled |
| GET | `/api/scheduler/daily-source-refresh/status` | scheduler status | no | no |
| GET | `/api/daily-brief/status` | daily brief/source freshness | no | no |

## Standard error shape

```json
{
  "ok": false,
  "error_code": "GRAPH_AUTH_STALE",
  "message": "Microsoft 365 needs to be reconnected.",
  "next_action": "Reconnect Microsoft 365 from this page.",
  "can_retry": true,
  "details_available": false
}
```

## Live refresh confirmation

A live refresh route must require explicit confirmation text, source selection, environment/config gate validation, and orchestrator-level gate validation. Frontend disabled state is not sufficient.
