# 01 Repo Truth Baseline

Generated: 2026-06-07T07:17:24.406486+00:00

Audit scope: `hb-personal-assistant` FastAPI / Vite React frontend analytics dashboard. Repository truth reviewed through the GitHub connector because the sandbox could not access `/Users/bobbyfetting/hb-personal-assistant` and network clone failed. No production source changes were made.


## Repository Identity

- Repository: `RMF112018/hb-personal-assistant`.
- Branch audited: `main`.
- Latest visible HEAD: `be470af1326c82b4c78be6103969e6a0622067be`.
- Latest visible HEAD note: `be470af...` adds `scripts/hb-claude-mcp-launcher.sh`; it is not a frontend production-readiness change.
- Latest relevant FastAPI/frontend commit: `4d902ce0ffb88e4e2e0eb362f7059cba0ff4928a`.

## Relevant Commit Chain Reviewed

- `be470af` — local MCP stdio launcher only.
- `4d902ce` — Prompt 08 / UI-08 nav active-state CSS, lucide-react upgrade, lockfile refresh, architecture record 176.
- `cc694c4` — Today compatibility routes and local role selector/default operator behavior.
- `3fbb831` — Prompt 14C Settings/evidence cleanup and Daily Brief test addition.
- `8beeb06` — Prompt 14B Settings / Connection Management UX surfaces.
- `6e55275` — Prompt 14A connection setup hardening.
- `0391431` — Prompt 13 security validation for no raw/no writeback UI route surface.
- `900c32f` — Prompt 11 Admin / Data Confidence surfaces.
- `8c2f21b` — Prompt 10 Daily Brief external Markdown workflow.
- `8a2afb1` — Prompt 09 Today / Projects / My Items screens.
- `26cab8f` — Prompt 07 dashboard read models.
- `2047e3e`, `a33af68`, `044495d`, `fb1413b`, `283c3a8`, `8d6d3a9`, `ded2a27` — earlier shell, auth, connection, keyword, sync governance, and analytics boundary setup.

## Package Versions / Dependencies

- `pyproject.toml` version: `1.3.0`.
- Optional `analytics-ui` extra exists with FastAPI, Uvicorn, and HTTPX.
- `frontend/package.json` version: `0.0.0`.
- Frontend scripts: `dev`, `build`, `typecheck`, `lint`, `preview`.
- Frontend runtime deps include React 19.2.6, React DOM 19.2.6, react-router-dom 6.26, TanStack Query 5, lucide-react 1.17, Recharts 2.12.
- Frontend dev deps include Vite 8, TypeScript 6, Tailwind 3.4.3, PostCSS, ESLint.
- `frontend/package-lock.json` exists and the root dependency block aligns with package.json.

## Commands / Validation Status

| Command | Result | Reason |
|---|---|---|
| `git status --short` | NOT_RUN | No local /Users/bobbyfetting/hb-personal-assistant worktree in sandbox; GitHub connector is read-only evidence source. |
| `git log --oneline -n 20` | PARTIAL_CONNECTOR | Recent commit chain inventoried with GitHub connector search_commits. |
| `git branch --show-current` | CONNECTOR_INFERRED_main | Repository default branch reported as main by GitHub connector. |
| `git rev-parse HEAD` | be470af1326c82b4c78be6103969e6a0622067be | Latest visible main commit from GitHub connector search_commits; latest frontend-specific commit is 4d902ce0ffb88e4e2e0eb362f7059cba0ff4928a. |
| `python -m pip show fastapi` | NOT_RUN | No repository virtualenv available in sandbox. |
| `python -m pytest tests/test_fastapi_analytics_app_shell.py` | NOT_RUN | No local repo clone; network clone failed due DNS. File exists in GitHub tree. |
| `python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py` | NOT_RUN | No local repo clone; file exists in GitHub tree. |
| `python -m pytest tests/test_fastapi_analytics_daily_brief.py` | NOT_RUN | No local repo clone; file exists in GitHub tree. |
| `python -m pytest tests/test_fastapi_analytics_settings.py` | NOT_RUN | No local repo clone; file exists in GitHub tree. |
| `python -m pytest tests/test_fastapi_analytics_connection_setup.py` | NOT_RUN | No local repo clone; file exists in GitHub tree. |
| `python -m pytest tests/test_fastapi_analytics_today.py` | GAP | File not found in GitHub tree. |
| `python -m ruff check src/hb_assistant/construction/analytics ...` | NOT_RUN | No local repo clone. |
| `python -m mypy src/hb_assistant/construction/analytics` | NOT_RUN | No local repo clone. |
| `cd frontend && npm install` | NOT_RUN | No local repo clone; package-lock exists and root deps align, but install was not executed. |
| `cd frontend && npm run lint` | NOT_RUN | No local repo clone. |
| `cd frontend && npm run typecheck` | NOT_RUN | No local repo clone. |
| `cd frontend && npm run build` | NOT_RUN | No local repo clone. |
| `git clone --depth 1 https://github.com/RMF112018/hb-personal-assistant.git /mnt/data/hb-personal-assistant-audit-clone` | FAILED | fatal: Could not resolve host: github.com from sandbox container. |
