# Launcher — macOS Desktop / Dock Shortcuts

How to launch the HB Assistant UI (Dev or Production) from a Dock icon, Desktop
double-click, or Automator app. The launcher owns opening the browser — shortcuts
only invoke the CLI and exit quickly.

## What the shortcut does

A shortcut runs exactly one command and returns:

```bash
hb-assistant launcher dev --open --json          # Dev
hb-assistant launcher production --open --json    # Production
```

`--open` performs the full user-facing flow:

1. Start the managed launcher session for the environment (backend, frontend,
   MCP, scheduler per profile config).
2. Resolve the environment's frontend URL (config → fallback
   `http://127.0.0.1:5173`).
3. Wait (bounded, default 30s) for the frontend URL to become reachable.
4. Open the frontend URL in the **default browser** (cross-platform
   `webbrowser.open`).
5. Return JSON status and detach — the shortcut process exits immediately.

The shortcut must **not** open the URL itself or run `vite` / `npm run dev` /
`uvicorn` directly. The launcher owns `--open`.

## Repo-owned shortcut scripts

Two ready-to-use wrappers ship in the repo:

- `scripts/shortcuts/hb-launcher-dev.command`
- `scripts/shortcuts/hb-launcher-production.command`

Each `cd`s to the repo root, prefers the venv `hb-assistant`, runs
`launcher <env> --open --json` under `nohup … &`, and exits. Double-clicking a
`.command` file in Finder runs it in Terminal; making it executable
(`chmod +x`, already set) lets it run on double-click.

### Dock / Desktop

Drag either `.command` file to the Dock (right side) or Desktop. Double-click to
launch. The Terminal window opens briefly and closes; the browser opens to the
environment's UI.

### Automator app (cleaner Dock icon)

1. Automator → New → **Application**.
2. Add a **Run Shell Script** action.
3. Set the script to (adjust the repo path):

   ```bash
   /Users/bobbyfetting/hb-personal-assistant/scripts/shortcuts/hb-launcher-dev.command
   ```

4. Save as `HB Assistant Dev.app` (and a second app for Production).
5. Drag the `.app` to the Dock. Optionally set a custom icon via Get Info.

The Automator app starts the launcher in the background and exits quickly; it
does not stay running and does not open the URL itself.

## Browser-mode lifecycle (important)

An ordinary browser window **cannot** reliably tell the launcher whether closing
the tab means *Quit* or *Run in Background*. So `--open` browser mode:

- reports `window_close_intercept_supported: false` and
  `lifecycle_control: "cli_or_ui_action_required"`;
- keeps launcher-managed background services (MCP, scheduler, backend) running
  per profile/session policy after you close the browser tab.

Closing the browser tab does **not** quit the app. Use the explicit lifecycle
commands:

```bash
hb-assistant launcher close --environment dev --action background --json   # keep services
hb-assistant launcher close --environment dev --action quit --json         # stop the UI process group
hb-assistant launcher stop  --environment dev --json                       # stop ALL managed processes
hb-assistant launcher status --environment dev --json                      # see frontend_url + process state
```

(Replace `dev` with `production` for the Production environment.)

## Optional: pywebview desktop window

If you install the optional `pywebview` package, you can request a managed
desktop window instead of a browser tab:

```bash
hb-assistant launcher dev --open --shell pywebview --json
```

When pywebview is installed it manages its own window and **can** intercept
window-close (`window_close_intercept_supported: true`). When it is **not**
installed, the launcher falls back to the default browser automatically, emits a
warning, and reports `open_method: "browser_fallback"` — it never fails. pywebview
remains optional and is never a hard dependency.

## Dev vs Production isolation

Dev and Production use separate app-support roots, DBs, and scheduler state. Dev
runs mock/local data by default; Production live reads stay config-gated. The
frontend URL is resolved per environment, so Dev and Production may point at
different URLs via the `launcher:` config block (see `config/config.example.yml`).
