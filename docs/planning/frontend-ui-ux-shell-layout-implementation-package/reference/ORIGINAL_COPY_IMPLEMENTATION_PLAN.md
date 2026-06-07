# Implementation Plan

Execute in order. Each prompt is intentionally small enough for a local agent to implement, validate, and commit independently.

## Prompt C01 — Production Shell and Navigation Copy Remediation

Objective: Remove dev/test/auth simulation copy and hidden/future chat affordances from normal navigation and chrome.

Scope:
- AppShell
- SupportNavigation
- navigationModel
- PageHeader titles
- footer copy

Acceptance criteria:
- No visible local dev role selector unless explicit dev flag is enabled
- No visible Chat disabled nav item
- Footer uses compact end-user Data Health language
- Admin nav label finalized

Validation:
- `cd frontend && npm run lint`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Prompt C02 — Auth Readiness API Client and Status Translation

Objective: Update frontend API client and copy mappers to consume Prompt A normalized readiness/account/data-quality routes using end-user labels.

Scope:
- frontend/src/lib/api.ts
- new frontend/src/lib/statusCopy.ts
- settings account components
- Data Quality footer/sidebar indicator

Acceptance criteria:
- Client helpers exist for /api/onboarding/readiness and /api/settings/connections/*
- 7 auth states are translated to plain labels
- No token/cache/route wording is rendered
- No sync starts from status checks

Validation:
- `python -m pytest tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py`
- `cd frontend && npm run typecheck && npm run build`

## Prompt C03 — Settings Guided Setup Rewrite

Objective: Rework Settings into end-user Account Connections, Project Connections, Daily Brief, Preferences, and Admin Approval sections.

Scope:
- SettingsPage split into components
- AccountConnectionsPanel
- ProjectConnectionsPanel
- DailyBriefSettingsPanel
- KeywordManagementPanel
- AdminSyncPanel

Acceptance criteria:
- No prompt IDs/FPR notes/raw-panel notes visible
- No JSON.stringify output visible
- No Load button labels remain
- Connection setup copy says connect/preview/save/request approval
- Daily Brief advanced setup is behind disclosure

Validation:
- `cd frontend && npm run lint && npm run typecheck && npm run build`

## Prompt C04 — Operational Page Copy Rewrite

Objective: Rewrite Today, Projects, Project Detail, and My Items copy to avoid implementation mechanics and focus on construction action.

Scope:
- TodayPage
- ProjectsPage
- ProjectDashboardPage
- Project* tab pages
- MyItemsPage
- shared empty states

Acceptance criteria:
- No FastAPI/uvicorn/read-model/source-evidence/domain-nav implementation copy on core pages
- No fallback JSON rendering in visible item rows
- Empty states direct user to Settings/Data Health appropriately
- Cost/time copy remains advisory without over-explaining

Validation:
- `cd frontend && npm run typecheck && npm run build`
- `manual smoke: Today/Projects/My Items with empty data and sample data`

## Prompt C05 — Admin Data Health Copy Translation

Objective: Translate Admin/Data Confidence into business-readable Data Health labels while keeping technical details available behind disclosures.

Scope:
- AdminDataConfidencePage
- Admin section title mapping
- role denied/access messages

Acceptance criteria:
- Section labels use Source Updates, Background Tasks, Safety Checks, Answer Quality, Access & Permissions, Data Coverage
- Role denied message is production-safe
- Technical details are opt-in
- No local dev role instructions in normal admin copy

Validation:
- `cd frontend && npm run typecheck && npm run build`

## Prompt C06 — Shared Error, Loading, Empty, and Disconnected-State Copy

Objective: Centralize and standardize all shared state copy and prevent raw backend errors from reaching normal UI.

Scope:
- ErrorState
- EmptyState
- LoadingState
- StaleDataBanner
- api error mapping

Acceptance criteria:
- HTTP status/detail strings are mapped to user-safe messages
- Developer details hidden behind explicit disclosure
- Disconnected-source state directs user to Settings
- Admin-only state is plain-language

Validation:
- `cd frontend && npm run lint && npm run typecheck && npm run build`

## Prompt C07 — Remove Unused Starter and Demo Copy

Objective: Remove or neutralize Vite/React starter files and other unused demo display copy from production frontend source.

Scope:
- frontend/src/App.tsx
- App.css
- starter assets if unused
- tests/import checks

Acceptance criteria:
- No Vite/React starter copy remains in production source
- No unused import path depends on App.tsx
- Build still green

Validation:
- `cd frontend && npm run lint && npm run typecheck && npm run build`

## Prompt C08 — Display Copy Regression Harness

Objective: Add automated forbidden-term scanning and a copy inventory so internal/dev copy does not return.

Scope:
- scripts/proofs or frontend scripts
- package.json script
- test fixtures
- allowlist

Acceptance criteria:
- Forbidden copy scan covers production frontend TS/TSX/CSS
- Allowlist covers docs/tests/dev-only only
- Scan fails on prompt IDs, local dev, raw panels, JSON.stringify outputs, backend route terms, Vite starter copy
- Evidence artifact records scan results

Validation:
- `python -m pytest tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_settings.py`
- `cd frontend && npm run copycheck && npm run lint && npm run typecheck && npm run build`
