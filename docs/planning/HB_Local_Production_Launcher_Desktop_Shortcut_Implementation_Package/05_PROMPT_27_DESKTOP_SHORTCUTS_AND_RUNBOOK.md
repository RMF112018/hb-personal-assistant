# Prompt 27 — Desktop Shortcuts and Launcher Runbook

## Objective

Add a low-friction desktop shortcut workflow and user-facing runbook for launching the HB analytics dashboard after Prompt 26 has implemented the stable launcher command.

The intended macOS experience is:

```text
Double-click "HB Dashboard.command"
  -> starts local production launcher
  -> opens browser to Today
```

## Preconditions

Prompt 26 must be complete.

Confirm:

```bash
hb-assistant analytics serve --no-open --port 8765
curl -f http://127.0.0.1:8765/health
curl -f http://127.0.0.1:8765/today
```

## Scope

Implement:

1. macOS `.command` launcher script.
2. Shortcut installation/copy instructions.
3. Optional Automator/Shortcuts wrapper instructions.
4. Troubleshooting guide.
5. Stop/restart guide.
6. Log location documentation.
7. Validation evidence template update.

## Non-Scope

Do not implement:

- Electron/Tauri app;
- signed macOS `.app`;
- Windows installer;
- background service/daemon;
- auto-start on login;
- cloud or network exposure;
- live sync changes.

## Recommended File Additions

Use repo truth for final paths, but recommended locations are:

```text
scripts/local/launch_hb_dashboard.command
docs/runbooks/local-dashboard-launcher.md
docs/runbooks/local-dashboard-desktop-shortcut.md
```

If the repo already has a launcher/runbook convention, follow it.

## macOS `.command` Script Requirements

The script must:

- use `#!/bin/zsh`;
- resolve the repo root robustly;
- activate `.venv` if present;
- fail clearly if `.venv` is missing;
- fail clearly if `hb-assistant` is unavailable;
- call the stable launcher command from Prompt 26;
- default to `--open`;
- not embed raw `uvicorn` commands unless there is no CLI alternative;
- keep terminal output readable;
- preserve error visibility.

Recommended script shape:

```bash
#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

if [[ ! -d ".venv" ]]; then
  echo "Python virtual environment not found at $REPO_ROOT/.venv"
  echo "Create it and install the project before launching the dashboard."
  read "?Press Enter to close..."
  exit 1
fi

source ".venv/bin/activate"

if ! command -v hb-assistant >/dev/null 2>&1; then
  echo "hb-assistant command not found after activating .venv."
  echo "Run: python -m pip install -e '.[analytics-ui]'"
  read "?Press Enter to close..."
  exit 1
fi

hb-assistant analytics serve --open

echo
read "?Dashboard stopped. Press Enter to close..."
```

Adjust command/path details to repo truth.

## Shortcut Setup Documentation

Document these options.

### Option A — Use `.command` file directly

```bash
chmod +x scripts/local/launch_hb_dashboard.command
```

Then:

- drag the `.command` file to Desktop; or
- create an alias and move the alias to Desktop.

### Option B — Create a cleaner macOS app wrapper

Use Automator or Shortcuts to run:

```bash
/Users/bobbyfetting/hb-personal-assistant/scripts/local/launch_hb_dashboard.command
```

This provides a cleaner app-like launch experience while still keeping the repo launcher script as source of truth.

## Acceptance Criteria

Prompt 27 is complete only when:

- macOS `.command` script exists and is executable.
- Double-clicking it starts the dashboard.
- Browser opens automatically.
- If setup is incomplete, the Terminal output gives a clear fix.
- Documentation explains install, launch, stop, restart, logs, and troubleshooting.
- Documentation warns that this is a local web launcher, not a desktop executable.
- No separate duplicate server logic is introduced.
- No live external APIs are called during shortcut launch.
- No source-system writeback occurs.
- No secrets or raw content are printed.

## Validation Commands

```bash
git status --short
test -f scripts/local/launch_hb_dashboard.command
test -x scripts/local/launch_hb_dashboard.command
zsh -n scripts/local/launch_hb_dashboard.command
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m ruff check scripts src/hb_assistant/construction/analytics tests
```

Manual validation:

1. Build frontend:
   ```bash
   cd frontend && npm run build
   ```
2. Double-click `.command` script.
3. Confirm browser opens.
4. Confirm Today loads.
5. Confirm Projects loads.
6. Confirm My Items loads.
7. Confirm Settings loads.
8. Confirm Admin/Data Confidence role behavior still works.
9. Stop the server with `Ctrl+C`.
10. Relaunch and confirm no stale process issue.

## Evidence Required

At closeout, provide:

- branch;
- HEAD SHA;
- shortcut script path;
- runbook paths;
- command used by shortcut;
- manual smoke-test results;
- screenshot optional but not required;
- validation command outputs;
- explicit no-writeback/no-live-external-call statement.
