# Prompt B — Microsoft Graph Local Auth Flow

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Implement the Microsoft Graph local-first authentication flow behind the normalized route contract using MSAL device-code auth, safe polling/status, silent refresh, and local disconnect.

## Scope

- Implement `POST /api/settings/connections/graph/auth/start`.
- Implement `GET /api/settings/connections/graph/auth/status?flow_id=...`.
- Implement or wire `POST /api/settings/connections/graph/disconnect-local`.
- Enhance Graph account status to verify cached auth with silent MSAL acquisition where possible.
- Support stale-but-refreshable and reauth-required states.
- Ensure startup readiness attempts silent refresh before prompting reauth.
- Return only safe account metadata: display/account hint, tenant hint, safe scopes, timestamps, status, messages.

## Non-Scope

- Do not implement Graph data sync.
- Do not request Outlook/Calendar project-matching behavior by default.
- Do not add source-system writeback.
- Do not expose token claims beyond safe identity hints.

## Likely Files Touched

- `src/hb_assistant/integrations/graph/*`
- `src/hb_assistant/config/*`
- `src/hb_assistant/construction/analytics/routes/*`
- `src/hb_assistant/construction/analytics/view_models/*`
- `tests/test_fastapi_analytics_auth_onboarding.py`
- `tests/test_fastapi_analytics_settings.py`

## Acceptance Criteria

- User can start Graph device-code auth from backend route.
- Backend stores device-flow/session state without exposing sensitive fields.
- Frontend-safe status polling reports pending/complete/expired/failed/cancelled.
- Connected status uses verified/silent token behavior when possible, not only file existence.
- Stale auth triggers silent refresh attempt before reauth prompt.
- Disconnect clears local cache/account state only.
- Tests prove no access token, refresh token, id token, bearer token, or cache path is serialized.

## Validation Commands

```bash
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py -k 'graph or readiness or secret'
python -m ruff check src/hb_assistant/integrations src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py
python -m mypy src/hb_assistant/construction/analytics
```

## Risk Notes

- Device-code user code is safe to display but should still be short-lived and not logged unnecessarily.
- Do not include `msal-token-cache.bin` path in any frontend response.
- If configured scopes are currently broader than product intent, preserve compatibility while documenting and enforcing no-writeback.
