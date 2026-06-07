# Execution Brief — Local Production Launcher + Desktop Shortcut

## Objective

Add a stable local production launch path for the HB analytics dashboard so the user can start the app with one command and, on macOS, a desktop shortcut.

The final experience should be:

1. User double-clicks a desktop shortcut or runs one command.
2. The local FastAPI backend starts.
3. The production-built frontend is served locally.
4. The browser opens automatically to the dashboard.
5. Logs are written to a predictable local location.
6. Duplicate instances and occupied ports are handled cleanly.
7. The app can be stopped or restarted without corrupting local state.

## Required Product Direction

The app remains a **local-first web app** at this stage.

It must not become:

- an Electron app,
- a Tauri app,
- a cloud-hosted dashboard,
- a browser extension,
- a public network service,
- a system-wide daemon,
- or a source-system writeback tool.

## Recommended Final User-Facing Command

Use a command similar to:

```bash
hb-assistant analytics serve --open
```

Acceptable equivalent command names:

```bash
hb-assistant dashboard serve --open
hb-assistant analytics-ui serve --open
```

The chosen command must be documented and stable.

## Recommended Shortcut Target

Create a repo-managed script such as:

```bash
scripts/local/launch_hb_dashboard.command
```

The script should call the stable CLI command, not duplicate low-level server startup logic.

## Implementation Principle

The shortcut should be a thin wrapper over the launcher command. The launcher command should be the source of truth.

Do not create separate, divergent launch paths for Terminal, shortcut, and documentation.
