# Test and Validation Plan

## Backend Tests To Add

Suggested new test file:

```text
tests/test_fastapi_analytics_auth_onboarding.py
```

Coverage:

- first-time readiness returns `/get-started` state.
- returning stale Graph auth triggers silent refresh before reauth.
- returning stale Procore auth triggers refresh-token attempt before reauth.
- failed refresh produces source-specific `reauth_required` action.
- readiness does not start sync.
- Graph auth start returns safe device-code metadata only.
- Graph auth status never returns token/cache path.
- Procore auth start returns safe authorization URL and flow ID.
- Procore callback validates state.
- Procore manual fallback is available but not primary.
- Procore exchange response does not include cache path.
- disconnect clears local auth state only.
- data-quality summary is safe for non-admin.
- data-quality detail is admin-only.
- project preview/save do not start sync.
- first-sync approval is required before sync eligibility.

## Frontend Tests To Add

Suggested tests if repo uses Vitest/React Testing Library:

- first-time readiness routes to `GetStartedPage`.
- returning stale auth shows refresh/reauth banner, not full first-time onboarding.
- Account Connections card starts Graph auth and displays code safely.
- Procore card opens authorization URL and polls status.
- Project Connections preview/save messaging states no sync starts.
- Sidebar Data Quality indicator renders dot/label and tooltip.
- Non-admin does not see diagnostic panel.
- Admin sees detail link/panel.

## Security Regression Tests

Add no-secret tests for API responses and rendered frontend text.

Forbidden strings:

```text
access_token
refresh_token
id_token
client_secret
Authorization
Bearer 
-----BEGIN
signed_url
download_url
msal-token-cache
procore-token-cache
```

## Required Validation Commands

```bash
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_settings.py
python -m mypy src/hb_assistant/construction/analytics

cd frontend
npm run lint
npm run typecheck
npm run build
```

## Manual Local Browser Smoke Test

1. Start backend.
2. Start frontend.
3. Clear or isolate local auth cache in a test-only profile.
4. Open app.
5. Confirm first-time session lands on `/get-started`.
6. Confirm Microsoft Graph card shows disconnected state.
7. Click Connect Microsoft 365.
8. Confirm device code appears and no token appears.
9. Complete or mock auth.
10. Confirm connected state.
11. Confirm no live sync starts.
12. Confirm Procore card shows disconnected state.
13. Click Connect Procore.
14. Confirm browser auth starts or fallback code mode is available.
15. Complete or mock callback.
16. Confirm connected state.
17. Enter Procore project homepage URL.
18. Preview parsed project.
19. Confirm preview does not start sync.
20. Save connection.
21. Confirm pending first-sync approval.
22. Confirm non-admin sidebar shows Data Quality dot and hover timestamp.
23. Confirm admin Settings view shows detailed diagnostics.
24. Confirm no tokens, secrets, cache paths, raw content, signed URLs, or download URLs appear anywhere in UI.
