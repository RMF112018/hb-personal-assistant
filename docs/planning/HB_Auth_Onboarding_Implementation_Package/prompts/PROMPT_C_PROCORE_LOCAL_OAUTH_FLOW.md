# Prompt C — Procore Local OAuth Flow

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Implement a usable Procore local OAuth flow with backend-controlled authorization start, localhost callback, state validation, safe status polling, refresh-token handling, manual code fallback, and local disconnect.

## Scope

- Implement `POST /api/settings/connections/procore/auth/start`.
- Implement `GET /api/settings/connections/procore/auth/callback`.
- Implement `GET /api/settings/connections/procore/auth/status?flow_id=...`.
- Implement `POST /api/settings/connections/procore/auth/exchange-code` as fallback only.
- Implement or wire `POST /api/settings/connections/procore/disconnect-local`.
- Use existing Procore OAuth/client/token-provider utilities where repo truth supports it.
- Add state validation and expiry.
- Add refresh-token attempt before reauth prompt.
- Remove any local `cache_path` or equivalent from frontend-facing responses.

## Non-Scope

- Do not implement Procore data sync.
- Do not write to Procore.
- Do not expose raw Procore API payloads.
- Do not require real Procore credentials in automated tests.

## Likely Files Touched

- `src/hb_assistant/integrations/procore/*`
- `src/hb_assistant/config/*`
- `src/hb_assistant/construction/analytics/routes/*`
- `src/hb_assistant/construction/analytics/view_models/*`
- `tests/test_fastapi_analytics_auth_onboarding.py`

## Acceptance Criteria

- Backend generates safe authorization URL and opaque flow ID.
- Callback validates state before token exchange.
- Token exchange and refresh happen only server-side.
- Manual code fallback exists but is not the primary UX.
- Connected status returns safe account/company hints only.
- Refresh is attempted before reauth prompt for returning users.
- Local disconnect clears local Procore auth state only.
- No token, secret, local cache path, authorization code, state token, raw callback query, or raw Procore payload appears in frontend responses or logs.

## Validation Commands

```bash
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py -k 'procore or readiness or secret'
python -m ruff check src/hb_assistant/integrations src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py
python -m mypy src/hb_assistant/construction/analytics
```

## Risk Notes

- If the local registered Procore app does not permit localhost redirect, retain OOB/manual fallback and document setup instructions.
- Callback HTML must be minimal and not include token details.
- Avoid storing OAuth flow state in a way that survives longer than necessary.
