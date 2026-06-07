# Prompt A — Auth Route Contract and Safe Status Models

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Create the normalized frontend-facing backend contract for onboarding, account connection status, auth refresh, project connection setup, admin approval, and data-quality summary/detail.

## Scope

- Add or refactor route family under `/api/onboarding/readiness` and `/api/settings/connections/*`.
- Add shared safe response models for auth state, onboarding state, account status, project connection preview/save, approval status, and data-quality summary.
- Preserve existing root-level routes if current tests depend on them, but do not require the frontend to call them directly.
- Make readiness capable of representing first-time, ready, degraded, reauth-required, and blocked states.
- Add explicit source auth states:
  - `never_connected`
  - `connected_valid`
  - `connected_refreshing`
  - `connected_stale_refreshable`
  - `connected_stale_reauth_required`
  - `connected_error`
  - `disconnected_by_user`

## Non-Scope

- Do not fully implement Graph device-code flow here beyond route shells/contracts if not already present.
- Do not fully implement Procore OAuth callback here beyond route shells/contracts if not already present.
- Do not build frontend UI here except API type alignment if unavoidable.

## Likely Files Touched

- `src/hb_assistant/construction/analytics/routes/*`
- `src/hb_assistant/construction/analytics/view_models/*`
- `src/hb_assistant/construction/analytics/api.py` or app route registration file
- `tests/test_fastapi_analytics_settings.py`
- `tests/test_fastapi_analytics_connection_setup.py`
- new `tests/test_fastapi_analytics_auth_onboarding.py`

## Acceptance Criteria

- `GET /api/onboarding/readiness` exists and returns safe startup state.
- `GET /api/settings/connections/accounts` exists and returns safe account summaries.
- `POST /api/settings/connections/auth/refresh` exists or is stubbed with safe status behavior for later prompts.
- Data-quality summary/detail route contracts exist.
- Project connection preview/save route contracts are normalized under `/api/settings/connections/projects/*`.
- Admin first-sync approval route contracts are normalized under `/api/settings/connections/admin/*`.
- No response includes tokens, secrets, local cache paths, raw external payloads, or raw content.

## Validation Commands

```bash
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py
python -m mypy src/hb_assistant/construction/analytics
```

## Risk Notes

- Do not break existing root route tests; add compatibility wrappers if necessary.
- Do not make readiness start sync.
- Do not make readiness require real external auth in tests.
