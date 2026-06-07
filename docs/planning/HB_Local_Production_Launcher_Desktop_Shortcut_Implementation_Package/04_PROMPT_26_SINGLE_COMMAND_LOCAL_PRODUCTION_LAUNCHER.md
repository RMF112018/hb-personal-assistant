# Prompt 26 — Single-Command Local Production Launcher

## Objective

Implement a stable, production-oriented local launcher command for the HB analytics dashboard.

The target user experience is:

```bash
hb-assistant analytics serve --open
```

The command should start the local backend, serve the production frontend, and open the browser to the app.

## Preconditions

Before starting this prompt, confirm that the previous frontend production-readiness package is complete.

Run:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m ruff check src/hb_assistant/construction/analytics
python -m mypy src/hb_assistant/construction/analytics
cd frontend && npm run lint && npm run typecheck && npm run build
```

If any command fails, stop and classify the failure as a preflight blocker unless the failure is already documented as intentionally deferred.

## Scope

Implement or finalize:

1. CLI command for local production dashboard launch.
2. Static frontend serving from the local backend.
3. Frontend build artifact detection.
4. Browser auto-open.
5. Configurable host/port.
6. Safe default binding to `127.0.0.1`.
7. Graceful shutdown behavior.
8. Clear terminal messages.
9. Log path convention.
10. Tests for launcher behavior where feasible.

## Non-Scope

Do not implement:

- Electron;
- Tauri;
- installer packaging;
- cloud deployment;
- network exposure by default;
- live sync startup;
- external API calls;
- source-system writeback;
- new dashboard features unrelated to startup.

## Repo Areas to Inspect

Inspect current repo truth before modifying:

```text
pyproject.toml
src/hb_assistant/cli.py
src/hb_assistant/construction/analytics/
src/hb_assistant/construction/analytics/api.py
frontend/package.json
frontend/vite.config.ts
tests/
docs/
```

The actual files may differ. Use repo truth.

## Recommended Implementation Design

### 1. CLI command

Add a command under the existing CLI structure.

Preferred user-facing command:

```bash
hb-assistant analytics serve --open
```

Options should include:

```text
--host 127.0.0.1
--port 8000
--open / --no-open
--reload false by default
--build optional, explicit only
--frontend-dist optional override
--log-file optional override
```

### 2. Static frontend serving

Serve `frontend/dist` after `npm run build`.

Recommended behavior:

- If `frontend/dist/index.html` exists, mount static files.
- Unknown non-API routes should return `index.html` for React Router fallback.
- `/api/*`, `/health`, and other backend routes must continue to work.
- Static serving must not weaken guardrails around API serialization.

### 3. Startup readiness

The launcher should open the browser only after the server is ready.

Preferred approach:

- start server;
- poll local `/health`;
- open browser to `/today` or `/`;
- continue serving until interrupted.

### 4. Port conflict behavior

If port is occupied:

- detect and print clear message;
- do not kill unknown processes by default;
- if the existing process responds as HB dashboard, print the URL and optionally open it;
- if unknown, instruct the user to choose another port or stop the process.

### 5. Logging

Use a predictable local log path.

Candidate paths:

```text
logs/analytics-dashboard.log
var/logs/analytics-dashboard.log
~/.hb-assistant/logs/analytics-dashboard.log
```

Use the repo’s existing conventions if present.

### 6. Tests

Add tests that verify:

- command exists;
- missing frontend build returns a clear error or warning;
- static route fallback works;
- API routes remain reachable;
- default host is loopback;
- unsafe host behavior is rejected or explicitly warned;
- `--open` can be disabled for tests;
- no live sync starts on launcher invocation.

## Acceptance Criteria

The prompt is complete only when:

- `hb-assistant analytics serve --no-open` starts locally.
- `hb-assistant analytics serve --open` opens the browser when run interactively.
- Built frontend is served without Vite dev server.
- `/today`, `/projects`, `/my-items`, `/admin`, and `/settings` load from the production local server.
- `/api/today` and other dashboard API routes still return expected responses.
- Missing frontend build gives a clear actionable message.
- The launcher binds to `127.0.0.1` by default.
- No live external APIs are called during startup.
- No source-system writeback occurs.
- No secrets/raw content are printed to terminal or logs.
- All relevant tests pass.

## Validation Commands

Run from repo root:

```bash
git status --short
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m ruff check src/hb_assistant/construction/analytics tests
python -m mypy src/hb_assistant/construction/analytics
cd frontend && npm run lint && npm run typecheck && npm run build
```

Launcher smoke:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
source .venv/bin/activate
hb-assistant analytics serve --no-open --port 8765
```

In another terminal:

```bash
curl -f http://127.0.0.1:8765/health
curl -f http://127.0.0.1:8765/api/today
curl -f http://127.0.0.1:8765/today
curl -f http://127.0.0.1:8765/projects
curl -f http://127.0.0.1:8765/my-items
curl -f http://127.0.0.1:8765/settings
```

Manual browser smoke:

```text
http://127.0.0.1:8765
```

Confirm it lands on Today or redirects to Today.

## Evidence Required

At closeout, provide:

- branch;
- HEAD SHA;
- files changed;
- command added;
- launcher URL;
- logs path;
- validation command outputs;
- browser smoke checklist;
- explicit statement that no live external APIs or source writeback occurred.
