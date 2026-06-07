# Component and File Plan

## Backend likely files

Confirm current names in P00. Likely areas:

- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/construction/analytics/routes/`
- `src/hb_assistant/construction/analytics/schemas/`
- `src/hb_assistant/construction/analytics/services/`
- Graph CLI/service modules
- Procore CLI/service modules
- source-refresh orchestration modules
- scheduler status modules

## Backend additions/adapters

- `routes/sources.py`
- `routes/environment.py`
- `routes/scheduler.py`
- `schemas/sources.py`
- `services/source_status.py`
- `services/graph_status.py`
- `services/procore_status.py`
- `services/source_refresh_api.py`

## Frontend likely files

- `frontend/src/lib/api.ts`
- `frontend/src/lib/sourceStatusTypes.ts`
- `frontend/src/lib/sourceStatusCopy.ts`
- `frontend/src/hooks/useSourceStatus.ts`
- `frontend/src/hooks/useSourceAction.ts`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/settings/SourceConnectionsPanel.tsx`
- `frontend/src/components/settings/GraphConnectionCard.tsx`
- `frontend/src/components/settings/ProcoreConnectionCard.tsx`
- `frontend/src/components/settings/SourceRefreshActions.tsx`
- `frontend/src/components/layout/DataQualityIndicator.tsx`
- `frontend/src/components/common/StatusBadge.tsx`
- `frontend/src/components/common/TechnicalDetails.tsx`

## Test files

- `tests/test_fastapi_analytics_sources_status.py`
- `tests/test_fastapi_analytics_graph_status.py`
- `tests/test_fastapi_analytics_procore_status.py`
- `tests/test_fastapi_analytics_source_refresh_actions.py`
- frontend component/hook/API tests using repo-conventional test paths.
