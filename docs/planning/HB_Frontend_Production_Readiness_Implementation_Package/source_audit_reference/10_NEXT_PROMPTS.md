# 10 Next Prompts

Generated: 2026-06-07T07:17:24.406486+00:00

Audit scope: `hb-personal-assistant` FastAPI / Vite React frontend analytics dashboard. Repository truth reviewed through the GitHub connector because the sandbox could not access `/Users/bobbyfetting/hb-personal-assistant` and network clone failed. No production source changes were made.


# Prompt 16 — Route/API Contract Hardening and Launch Blockers

You are working on the `hb-personal-assistant` repository at `/Users/bobbyfetting/hb-personal-assistant`.

Objective: eliminate current browser-breaking FastAPI/frontend contract mismatches before any product polish. Repository truth is authoritative. Do not broaden scope.

Scope:
1. Fix Project tab response-shape handling so `/projects/all/meetings`, `/projects/all/field-operations`, `/projects/all/cost-time`, and project-specific equivalents render from backend object envelopes without TypeError.
2. Resolve My Items frontend/backend route mismatch by either adding safe section endpoints derived from `build_my_items()` or refactoring frontend to use only `/api/my-items`.
3. Remove or implement the unused `/api/today/important` API client export.
4. Replace BrowserRouter-incompatible `#/settings` and `#/today` links with React Router `Link` targets.
5. Add clear Admin role-denied UI for non-admin local roles without weakening backend role guards.
6. Update route/API inventories and tests to reflect the final contract.

Non-scope: visual redesign, new source integrations, active chat, source-system writeback, live sync triggering.

Acceptance criteria:
- No expected frontend API call returns 404 during local smoke.
- Project tab pages render without object/array runtime errors.
- My Items renders without failed section-query noise.
- Admin page clearly distinguishes non-admin role from loading/error.
- Chat remains disabled and inaccessible.
- No production source raw data, tokens, secrets, signed URLs, raw email/calendar/document bodies, raw prompts/responses, or PEM material are serialized.

Validation commands:
```bash
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py tests/test_fastapi_analytics_daily_brief.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py
python -m mypy src/hb_assistant/construction/analytics
cd frontend && npm install && npm run lint && npm run typecheck && npm run build
```

Manual smoke:
- Start backend on port 8000.
- Start frontend on port 5173.
- Visit `/today`, `/projects`, `/projects/all`, `/projects/all/meetings`, `/projects/all/field-operations`, `/projects/all/cost-time`, `/my-items`, `/settings`, `/admin` as operator and admin.
- Confirm no expected API 404s and no blocking console errors.

Risk notes:
- If new backend routes are added, update `tests/test_fastapi_analytics_app_shell.py` OpenAPI path set.
- Prefer thin frontend adapters over duplicating backend intelligence.
- Keep Admin role guards server-side; UI improvements must not weaken access control.
