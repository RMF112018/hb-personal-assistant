# Validation Matrix

## Automated Validation

| Area | Command | Expected Result |
|---|---|---|
| Git status | `git status --short` | Only intended implementation files changed |
| Python analytics tests | `python -m pytest tests/test_fastapi_analytics_app_shell.py` | Pass |
| Dashboard read-model tests | `python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py` | Pass |
| Daily Brief tests | `python -m pytest tests/test_fastapi_analytics_daily_brief.py` | Pass |
| Settings tests | `python -m pytest tests/test_fastapi_analytics_settings.py` | Pass |
| Connection setup tests | `python -m pytest tests/test_fastapi_analytics_connection_setup.py` | Pass |
| Ruff | `python -m ruff check src/hb_assistant/construction/analytics tests scripts` | Pass, or scripts path adjusted if absent |
| Mypy | `python -m mypy src/hb_assistant/construction/analytics` | Pass |
| Frontend lint | `cd frontend && npm run lint` | Pass |
| Frontend typecheck | `cd frontend && npm run typecheck` | Pass |
| Frontend build | `cd frontend && npm run build` | Pass |
| Shortcut syntax | `zsh -n scripts/local/launch_hb_dashboard.command` | Pass |

## Launcher Smoke Validation

Start server:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
source .venv/bin/activate
hb-assistant analytics serve --no-open --port 8765
```

In second terminal:

```bash
curl -f http://127.0.0.1:8765/health
curl -f http://127.0.0.1:8765/api/today
curl -f http://127.0.0.1:8765/today
curl -f http://127.0.0.1:8765/projects
curl -f http://127.0.0.1:8765/my-items
curl -f http://127.0.0.1:8765/admin
curl -f http://127.0.0.1:8765/settings
```

## Manual Browser Validation

Open:

```text
http://127.0.0.1:8765
```

Confirm:

- Root lands on Today or redirects to Today.
- Today renders without console-breaking errors.
- Projects renders.
- My Items renders.
- Admin/Data Confidence renders or blocks appropriately by role.
- Settings renders.
- Refreshing nested routes does not 404.
- Browser back/forward works.
- No Vite dev server is required.
- No active chat route appears.
- No secrets/raw content appears.

## Desktop Shortcut Validation

On macOS:

```bash
chmod +x scripts/local/launch_hb_dashboard.command
open scripts/local/launch_hb_dashboard.command
```

Confirm:

- Terminal opens.
- Launcher starts.
- Browser opens.
- User sees clear messages.
- `Ctrl+C` stops the server.
- Relaunch works.
