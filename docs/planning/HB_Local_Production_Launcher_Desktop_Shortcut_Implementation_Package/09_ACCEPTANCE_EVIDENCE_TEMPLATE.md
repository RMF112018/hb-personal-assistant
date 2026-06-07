# Acceptance Evidence Template

Use this template for the implementation closeout.

## Summary

- Branch:
- HEAD SHA:
- Package executed:
- Prompt(s) completed:
- Date/time:
- Implementer:

## Files Changed

```text
<list files changed>
```

## Launcher Command

Final supported command:

```bash
<command>
```

Supported options:

```text
<options>
```

## Shortcut Path

```text
<path to .command script>
```

## Log Path

```text
<log path>
```

## Validation Commands Run

Paste outputs or summarized pass/fail status:

```bash
git status --short
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m ruff check src/hb_assistant/construction/analytics tests scripts
python -m mypy src/hb_assistant/construction/analytics
cd frontend && npm run lint && npm run typecheck && npm run build
zsh -n scripts/local/launch_hb_dashboard.command
```

## Local Launcher Smoke

| Check | Pass/Fail | Notes |
|---|---|---|
| `hb-assistant analytics serve --no-open` starts |  |  |
| Built frontend served without Vite dev server |  |  |
| Browser opens with `--open` |  |  |
| `/health` returns success |  |  |
| `/api/today` returns success |  |  |
| `/today` loads |  |  |
| `/projects` loads |  |  |
| `/my-items` loads |  |  |
| `/admin` behavior correct by role |  |  |
| `/settings` loads |  |  |
| Refreshing nested routes does not 404 |  |  |
| Port conflict handled clearly |  |  |
| Missing frontend build handled clearly |  |  |
| Shortcut double-click works |  |  |

## Guardrail Confirmation

Confirm each statement:

- [ ] No production source-system writeback occurred during validation.
- [ ] No live external APIs were called during launch validation.
- [ ] No operator DB writes occurred except approved runtime metadata/logging, if applicable.
- [ ] No auth cache contents were written to evidence.
- [ ] No tokens/secrets/signed URLs were printed or written.
- [ ] No raw email bodies were printed or written.
- [ ] No raw document text was printed or written.
- [ ] No active in-app chat interface was introduced.
- [ ] Dashboard binds to `127.0.0.1` by default.

## Known Issues / Deferred Items

```text
<list anything deferred>
```

## Recommended Next Step

```text
<next prompt or package>
```
