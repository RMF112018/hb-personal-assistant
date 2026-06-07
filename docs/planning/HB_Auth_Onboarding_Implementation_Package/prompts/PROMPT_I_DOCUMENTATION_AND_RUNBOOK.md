# Prompt I — Documentation and Runbook

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Update documentation and operator runbooks after implementation and validation are complete.

## Scope

- Document first-time Get Started flow.
- Document Microsoft 365 device-code auth.
- Document Procore OAuth callback and manual fallback.
- Document stale-auth automated refresh and reauth behavior.
- Document Project Connections preview/save/admin approval flow.
- Document Data Quality indicator meanings.
- Document security guardrails and no-writeback posture.
- Document local smoke testing.

## Non-Scope

- Do not claim external API sync is production-ready unless implementation and tests prove it.
- Do not include tokens, screenshots with codes, cache paths, or secrets.
- Do not document unsupported deployment assumptions.

## Likely Files Touched

- `docs/architecture/*`
- `docs/runbooks/*`
- `README.md` if repo conventions require it
- `docs/evidence/*` if repo uses evidence packets for implementation closeout

## Acceptance Criteria

- Docs match implemented routes and UI labels.
- Docs explain that connect/preview/save do not start sync.
- Docs explain first live sync requires admin approval.
- Docs explain non-admin vs admin Data Quality visibility.
- Docs include validation commands and expected results.
- Docs contain no secrets or real auth artifacts.

## Validation Commands

```bash
git diff --check
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_settings.py
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Risk Notes

- Avoid roadmap-style claims that are not repo-true.
- Label manual Procore code fallback as fallback, not primary path.
