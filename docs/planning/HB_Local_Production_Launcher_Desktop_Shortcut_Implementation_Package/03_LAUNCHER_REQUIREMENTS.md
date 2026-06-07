# Launcher Requirements

## Functional Requirements

### FR-01 — Stable CLI command

Add a stable CLI command for local production dashboard launch.

Preferred command:

```bash
hb-assistant analytics serve --open
```

The command must:

- start the FastAPI analytics app;
- serve built frontend assets or fail with a clear instruction to build them;
- open the browser when `--open` is provided;
- default to `127.0.0.1`;
- default to a predictable port;
- allow `--port`;
- allow `--host`, but warn or reject unsafe network exposure unless explicitly overridden;
- write logs to a predictable local path;
- handle `Ctrl+C` cleanly.

### FR-02 — Frontend build integration

The launcher must support a production frontend.

Acceptable approaches:

1. Serve `frontend/dist` from FastAPI.
2. Run a local static file server from Python.
3. Delegate to a repo-approved production frontend server.

Preferred approach: serve `frontend/dist` from the FastAPI app or an analytics-specific static mount.

Do not use the Vite dev server as the production local launcher path.

### FR-03 — Build preflight

The launcher must detect missing frontend build artifacts.

If `frontend/dist` is missing, it should either:

- fail with a clear message:
  ```text
  Frontend build not found. Run: cd frontend && npm run build
  ```
- or support an explicit `--build` flag that runs the build.

Do not run `npm install` automatically.

### FR-04 — Port/process handling

The launcher must handle:

- backend port already in use;
- stale PID files;
- existing dashboard server already running;
- browser open when server is ready, not before;
- graceful shutdown.

### FR-05 — Desktop shortcut script

Add a repo-managed macOS `.command` script.

Recommended path:

```text
scripts/local/launch_hb_dashboard.command
```

The script must:

- resolve the repo path reliably;
- activate `.venv` or use the local Python environment according to repo conventions;
- call the stable CLI command;
- avoid duplicating uvicorn/app-factory details;
- keep the Terminal window open long enough to show actionable errors.

### FR-06 — Documentation

Document:

- initial setup;
- how to build frontend assets;
- how to run the launcher;
- how to create/use the desktop shortcut;
- how to stop/restart;
- where logs are stored;
- common failures and fixes.

## Non-Functional Requirements

### NFR-01 — Local-first

The app must remain local-first and bind to loopback by default.

### NFR-02 — Low-friction

The shortcut must reduce startup friction for a non-engineering user.

### NFR-03 — Observable but not noisy

Logs must be available but the normal user experience should not feel like an engineering console.

### NFR-04 — Safe failure

If startup fails, the user must receive a clear next step.

### NFR-05 — No source-system writeback

Startup must not initiate external writeback or live sync.

### NFR-06 — No secret leakage

Logs and terminal output must not expose tokens, secrets, signed URLs, raw emails, raw documents, auth cache material, or PEM content.
