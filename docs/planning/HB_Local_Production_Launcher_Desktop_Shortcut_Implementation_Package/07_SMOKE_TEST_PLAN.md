# Smoke Test Plan — Local Launcher and Shortcut

## Test 1 — Production build available

1. Run:
   ```bash
   cd frontend && npm run build
   ```
2. Confirm:
   ```text
   frontend/dist/index.html exists
   ```

Expected: production assets are generated.

## Test 2 — CLI launcher starts

1. Run:
   ```bash
   hb-assistant analytics serve --no-open --port 8765
   ```

Expected:

- server starts;
- host is `127.0.0.1`;
- port is `8765`;
- terminal output includes dashboard URL;
- no browser opens when `--no-open` is used.

## Test 3 — Static frontend served

Open:

```text
http://127.0.0.1:8765
```

Expected:

- app loads;
- root lands on Today;
- no Vite dev server is required.

## Test 4 — React Router fallback

Open directly:

```text
http://127.0.0.1:8765/projects
http://127.0.0.1:8765/my-items
http://127.0.0.1:8765/settings
```

Expected:

- each route returns the app shell;
- no server-side 404;
- frontend route renders.

## Test 5 — API routes still work

Run:

```bash
curl -f http://127.0.0.1:8765/api/today
curl -f http://127.0.0.1:8765/health
```

Expected:

- API responses are returned;
- static fallback does not intercept API routes.

## Test 6 — Port conflict

Start server on `8765`, then attempt another:

```bash
hb-assistant analytics serve --no-open --port 8765
```

Expected:

- second process gives clear conflict message;
- it does not kill an unknown process;
- it recommends another port or opening existing dashboard if detectable.

## Test 7 — Missing frontend build

Temporarily move `frontend/dist` aside.

Expected:

- launcher fails clearly or instructs:
  ```bash
  cd frontend && npm run build
  ```
- it does not silently fall back to Vite dev server.

## Test 8 — macOS shortcut

Run:

```bash
open scripts/local/launch_hb_dashboard.command
```

Expected:

- Terminal opens;
- server starts;
- browser opens;
- dashboard loads;
- Terminal output is understandable.

## Test 9 — Guardrails

During startup, confirm:

- no live external APIs are called;
- no source-system writeback occurs;
- no auth token values are printed;
- no raw email body or document text is printed;
- no active chat route is exposed.

## Test 10 — Restart

Stop with `Ctrl+C`.

Relaunch from shortcut.

Expected:

- no stale PID issue;
- app starts normally;
- browser opens normally.
