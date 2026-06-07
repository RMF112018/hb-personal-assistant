# P06 — Settings Guided Setup and Normalized Route Consumption

## Objective

Rewrite Settings into guided, user-facing setup panels and update frontend client/hooks to consume existing normalized readiness/account/project/data-quality routes.

## Scope

Likely files:

- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/settings/AccountConnectionsPanel.tsx`
- new/refactored `frontend/src/components/settings/ProjectConnectionsPanel.tsx`
- new/refactored `frontend/src/components/settings/DailyBriefSettingsPanel.tsx`
- new/refactored `frontend/src/components/settings/KeywordManagementPanel.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/hooks/useOnboardingReadiness.ts`
- new `frontend/src/hooks/useDataQualitySummary.ts`
- shared `statusCopy.ts` / `errorCopy.ts`

## Existing normalized routes to prefer

Confirm current route names from repo truth, then use the normalized contracts already exposed by backend tests, expected to include:

- `/api/onboarding/readiness`
- `/api/settings/connections/accounts`
- `/api/settings/data-quality/summary`
- data-quality detail route(s) if already present

## Required copy remediation

Remove from normal Settings UI:

- Prompt IDs such as `Prompt 14B`, `Prompt 20`;
- internal gap IDs such as `FPR-004`;
- labels like `Load Accounts Status`, `Load Projects`, `Load Source Scope`;
- raw panels / raw JSON / `JSON.stringify` output;
- `preview→save (14A)` implementation labels;
- Daily Brief Markdown/MCP/scheduled prompt internals in the normal view.

Target sections:

- Account Connections
- Project Connections
- Daily Brief
- Preferences
- Data Health / Admin Approval where allowed

Preferred action labels:

- `Check connection status`
- `Review project connections`
- `Save project selections`
- `Request update approval`
- `Check for today’s brief`
- `Open Data Health`

## Non-scope

- Do not start live sync from status checks.
- Do not change backend safety guardrails.
- Do not implement new OAuth flows in this prompt.

## Acceptance criteria

- Settings normal UI is free of prompt IDs, raw/debug language, and loader/test-harness labels.
- Frontend readiness/account summary uses normalized routes where available.
- Daily Brief technical details are behind collapsed advanced disclosure.
- Project keyword management is business-facing and does not expose project keys/JSON as the default UX.
- Backend contract tests pass.

## Validation

```bash
cd /Users/bobbyfetting/hb-personal-assistant
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py

cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
```
