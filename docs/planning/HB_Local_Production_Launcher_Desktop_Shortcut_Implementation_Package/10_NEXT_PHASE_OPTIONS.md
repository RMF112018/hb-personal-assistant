# Next Phase Options After Local Launcher

After the single-command launcher and desktop shortcut are stable, choose one of these paths.

## Option A — Stop at Local Web App + Shortcut

Recommended near-term default.

Benefits:

- lowest complexity;
- easiest to debug;
- aligns with current FastAPI/Vite architecture;
- avoids installer/signing burden;
- suitable for personal/local-first production use.

## Option B — macOS App Wrapper

Add a lightweight Automator or Shortcuts app around the `.command` script.

Benefits:

- cleaner icon;
- easier Desktop/Dock usage;
- no major architecture change.

Limitations:

- still not a true packaged app;
- still depends on repo and `.venv`.

## Option C — pywebview + PyInstaller

Python-first packaged local desktop app.

Benefits:

- can bundle backend and frontend into one executable-style app;
- avoids Electron size;
- keeps Python runtime central.

Risks:

- packaging local databases/auth caches/logs must be designed carefully;
- Mac notarization and Windows signing may be needed;
- app shutdown/process handling becomes more complex.

## Option D — Tauri

Modern lightweight native wrapper around web UI.

Benefits:

- smaller than Electron;
- strong native-app feel;
- good long-term option.

Risks:

- introduces Rust/toolchain requirements;
- Python backend bundling/orchestration still needs design;
- security model must be explicitly configured.

## Option E — Electron

Full-featured desktop wrapper.

Benefits:

- familiar desktop app packaging;
- broad ecosystem;
- can manage local windows, tray, auto-update.

Risks:

- heavier footprint;
- duplicates browser runtime;
- more packaging complexity;
- must carefully manage backend child process.

## Recommendation

Do not choose Options C, D, or E until:

- local production launcher is stable;
- dashboard routes are complete;
- settings and auth cache flows are stable;
- local logs/runtime directories are settled;
- shutdown/restart behavior is reliable;
- no live sync starts unintentionally;
- a packaging threat model exists.

The recommended next step after this package is a **desktop packaging feasibility audit**, not immediate executable packaging.
