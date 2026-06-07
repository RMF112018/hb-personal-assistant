# 06 Validation Matrix

## Backend Validation

Run the targeted analytics suite after any backend route/view-model changes:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
source .venv/bin/activate
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m pytest tests/test_fastapi_analytics_today.py
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py tests/test_fastapi_analytics_daily_brief.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_today.py
python -m mypy src/hb_assistant/construction/analytics
```

If `tests/test_fastapi_analytics_today.py` does not exist, create it under Prompt 17 and document that it was an audit-confirmed gap.

## Frontend Validation

Run after every frontend prompt:

```bash
cd /Users/bobbyfetting/hb-personal-assistant/frontend
npm install
npm run lint
npm run typecheck
npm run build
```

Do not use `--legacy-peer-deps` as a hidden permanent solution.

## Browser Smoke Validation

Run backend and frontend locally:

```bash
# Terminal 1
cd /Users/bobbyfetting/hb-personal-assistant
source .venv/bin/activate
python -m uvicorn "hb_assistant.construction.analytics.api:create_app" --factory --port 8000

# Terminal 2
cd /Users/bobbyfetting/hb-personal-assistant/frontend
npm run dev
```

Validate at `http://localhost:5173`:

- `/` redirects to `/today`.
- `/today` loads with no blocking console errors.
- `/projects` loads.
- `/projects/all/overview` loads.
- `/projects/all/meetings` loads.
- `/projects/all/field-operations` loads.
- `/projects/all/cost-time` loads.
- `/my-items` loads with no expected API 404s.
- `/admin` shows an admin-required state for default/operator role.
- `/admin` loads admin data when local dev role is set to admin.
- `/settings` loads.
- No active chat route is accessible.

## Safety Validation

Run grep or scripted checks as appropriate:

```bash
grep -R "Raw response" -n frontend/src || true
grep -R "alert(" -n frontend/src || true
grep -R "#/" -n frontend/src || true
grep -R "join_url\|joinUrl\|bodyPreview\|raw_body\|rawBody\|access_token\|refresh_token\|signed_url\|download_url\|BEGIN PRIVATE KEY" -n frontend/src src/hb_assistant/construction/analytics tests docs/evidence/frontend-production-readiness-implementation || true
```

Any hits must be reviewed. Some test fixture strings may be acceptable only if they assert redaction/non-serialization and do not contain real secrets or real raw content.
