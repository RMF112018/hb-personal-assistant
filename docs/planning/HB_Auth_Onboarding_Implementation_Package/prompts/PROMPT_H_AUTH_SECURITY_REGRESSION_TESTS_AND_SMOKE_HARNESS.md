# Prompt H — Auth/Security Regression Tests and Local Smoke Harness

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Add comprehensive regression tests and a local smoke harness for auth onboarding, frontend route behavior, security hygiene, no-sync setup behavior, and data-quality surfaces.

## Scope

- Add backend tests for all normalized auth/onboarding/data-quality routes.
- Add frontend tests if repo tooling supports them.
- Add no-secret/no-token serialization tests.
- Add no-sync-from-setup tests.
- Add first-time vs returning stale-auth tests.
- Add admin vs non-admin data-quality tests.
- Add local smoke runbook or script if repo conventions support it.

## Non-Scope

- Do not require real Graph or Procore credentials in CI.
- Do not initiate live OAuth in automated tests.
- Do not write to operator DB except isolated test DB/temp fixtures.

## Likely Files Touched

- `tests/test_fastapi_analytics_auth_onboarding.py`
- `tests/test_fastapi_analytics_connection_setup.py`
- `tests/test_fastapi_analytics_settings.py`
- frontend test files if present
- `scripts/proofs/*` only if repo uses proof scripts for this phase

## Acceptance Criteria

- Tests fail if any frontend-facing route serializes forbidden token/secret/cache/path fields.
- Tests fail if preview/save/auth/approval starts sync.
- Tests cover first-time `/get-started` readiness.
- Tests cover returning stale auth refresh-before-reauth behavior.
- Tests cover non-admin Data Quality summary and admin detail.
- Existing analytics tests remain green or documented if unrelated pre-existing failures exist.

## Validation Commands

```bash
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_settings.py
python -m mypy src/hb_assistant/construction/analytics
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Risk Notes

- Avoid brittle UI snapshot tests containing timestamps; normalize dates.
- Mock MSAL and Procore token provider behavior.
- Use temporary test directories for auth cache tests.
