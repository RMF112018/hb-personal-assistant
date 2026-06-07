# Product and Architecture Decision

## Decision

The HB analytics dashboard should remain a local-first web app for the next implementation step, with a single production launcher and desktop shortcut support.

A native executable wrapper is deferred.

## Rationale

The current architecture is already split into:

- a Python/FastAPI backend;
- a React/Vite frontend;
- local database/auth/cache/runtime dependencies;
- local-first workflows;
- optional external-agent interactions.

A single local launcher is the lowest-risk way to make the app usable without prematurely bundling an unstable runtime into a desktop app.

## Approved Target

```text
Double-click shortcut
  -> launcher script
    -> hb-assistant analytics serve --open
      -> starts local FastAPI server
      -> serves production frontend assets
      -> opens browser to Today
```

## Deferred Target

```text
Packaged .app / .exe
  -> bundled backend runtime
  -> embedded browser/webview
  -> managed local data directory
  -> signed/notarized installer
```

Deferred packaging options include:

- Tauri;
- Electron;
- pywebview + PyInstaller;
- platform-native app wrapper.

## Non-Negotiable Guardrails

- Bind only to `127.0.0.1` by default.
- Do not expose the dashboard on `0.0.0.0` by default.
- Do not start live external syncs during launcher startup.
- Do not print secrets, tokens, auth cache contents, signed URLs, raw email bodies, or raw document content.
- Do not modify operator DB data during launch other than safe runtime metadata/logging if already approved by repo conventions.
- Do not require users to run raw `uvicorn` or raw `npm` commands for normal use after this package is complete.
