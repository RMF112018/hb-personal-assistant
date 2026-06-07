# Target Architecture

## Principle

The frontend never calls Microsoft Graph or Procore directly. It calls the local backend only. The backend exposes safe source status, backend-controlled auth workflows, and explicitly gated refresh commands.

## Target layers

```text
Frontend
  Settings / Connections
  Data Quality sidebar footer
  typed API client
        |
Backend API
  /api/environment
  /api/sources/status
  /api/sources/graph/status
  /api/sources/procore/status
  /api/sources/*/auth/*
  /api/sources/refresh/*
  /api/scheduler/*/status
  /api/daily-brief/status
        |
Service adapters
  GraphStatus/Auth
  ProcoreStatus/Auth
  SourceRefresh
  SchedulerStatus
        |
Existing CLI/services
  hb-assistant graph ...
  hb-assistant procore ...
  hb-assistant construction-agent refresh-sources ...
        |
Local app-support root / DB / token cache / receipts
```

## Frontend state model

Use normalized fields:

- `environment.mode`
- `environment.sourceRefreshMode`
- `graph.connectionState`
- `graph.scopes.status`
- `graph.lastLocalSyncAt`
- `graph.liveReads.enabled`
- `procore.connectionState`
- `procore.mapping.mappedProjectCount`
- `procore.lastLocalSyncAt`
- `procore.liveReads.enabled`
- `refresh.lastReceipt`
- `scheduler.nextRunAt`

## Auth workflows

Graph should use existing MSAL/token-cache utilities. Procore should use backend-controlled OAuth. Tokens remain server-side.

## Refresh workflows

- Status: metadata-only.
- Dry-run: preview/receipt only.
- Local: update local/mock Dev data only.
- Live: gated and confirmation-required.
