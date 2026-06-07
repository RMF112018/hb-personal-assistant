# 188 — Launcher Open Frontend

**Objective:** make launching Dev or Production a one-action, user-facing flow that
automatically opens the frontend UI. The pure-Python launcher already starts the
managed processes (backend, frontend, MCP, scheduler) and persists session state, but
it never opened the UI — operators had to paste `http://127.0.0.1:5173` by hand. This
adds a `launcher <env> --open` flow that starts the session, waits for the frontend to
become reachable, opens it in the default browser, and detaches so a Dock/Automator
shortcut exits quickly. Builds on [187](187-cross-platform-launcher-and-scheduler.md).

## CLI surface

```
hb-assistant launcher dev        --open [--open-timeout-seconds N] [--shell browser|pywebview] [--frontend-url URL] --json
hb-assistant launcher production --open [--open-timeout-seconds N] [--shell browser|pywebview] [--frontend-url URL] --json
```

Without `--open` the commands behave exactly as before (`start`, optional `--plan`).
`status`, `close`, `stop`, `snapshot-dev-db` are unchanged.

## Flow (`LauncherService.open_session`)

1. Resolve the frontend URL and its source (see below).
2. `start(plan_only=...)` — spawn/plan the profile's process specs; persist the
   resolved URL on the session state.
3. `wait_for_frontend(url, timeout)` — bounded readiness poll.
4. Open the UI: `browser` → `webbrowser.open`; `pywebview` → managed window if
   installed, else browser fallback.
5. Merge the open-specific fields into `status()` and return JSON.

## Frontend URL resolution

Order: **CLI `--frontend-url`** → env-specific `launcher.<env>.frontend_url`
(config) → profile/process-spec → fallback `http://127.0.0.1:5173`. The resolved
value and its provenance are reported as `frontend_url` + `frontend_url_source`
(`cli | config | fallback`). Dev and Production may resolve to different URLs via the
new `launcher:` config block (`config/config.example.yml`). `launcher status` reports
the resolved URL deterministically (not only after a start). The static-dist frontend
process spec derives its `http.server` port from the resolved URL so the served port
and the opened URL always agree.

## Readiness wait (`frontend_open.wait_for_frontend`)

Bounded loop over a LOCAL URL using `urllib.request.urlopen` with a short per-probe
timeout; any HTTP response (incl. 4xx/5xx) counts as reachable, connection
refusals/timeouts are swallowed and retried. Default timeout 30s (config/CLI
overridable), interval 1s, deadline computed via `time.monotonic`. Never requires
internet access. On timeout it returns a warning and the intended URL is still
reported (`frontend_reachable=false`).

## Browser open (`frontend_open.open_browser`)

Cross-platform `webbrowser.open(url, new=2)` inside try/except — non-blocking and
non-fatal. Failure surfaces as `frontend_opened=false` + a warning, never a crash.
macOS `open` is used only in the repo-owned shortcut helpers, never in core launcher
code.

## Browser-mode lifecycle

An ordinary browser window cannot reliably intercept close to choose Quit vs
Run-in-Background. Browser mode therefore reports:

- `window_close_intercept_supported: false`
- `lifecycle_control: "cli_or_ui_action_required"`

and keeps launcher-managed background services running. Quit / Run-in-Background stay
explicit via `launcher close --action quit|background` (and `launcher stop`).

## Optional pywebview

`--shell pywebview` uses the lazy `webview_shell.pywebview_available()` probe. When
installed, pywebview manages its own window and can intercept close
(`window_close_intercept_supported: true`, `lifecycle_control: "pywebview_window"`).
When **not** installed, the launcher falls back to the browser, emits a warning, and
reports `open_method: "browser_fallback"`, `requested_shell: "pywebview"`,
`actual_shell: "browser"` — it never fails and never hard-imports `webview`.

## Open-result JSON (added to `status()` keys)

`frontend_url`, `frontend_url_source`, `frontend_reachable`, `frontend_opened`,
`open_method`, `requested_shell`, `actual_shell`, `timeout_seconds`,
`window_close_intercept_supported`, `lifecycle_control`, `warnings`. Existing status
keys (environment, processes/session, db_path, app-support via `profile`, build_sha,
executable/python paths, config_profile) are preserved.

## macOS shortcuts

`scripts/shortcuts/hb-launcher-{dev,production}.command` run
`launcher <env> --open --json` under `nohup … &` and exit quickly. They never open the
URL or run Vite/uvicorn directly — the launcher owns `--open`. Setup is documented in
`docs/runbooks/launcher-macos-shortcuts.md`.

## Guardrails

`--open` adds no live external reads and triggers no source refresh by itself —
scheduler startup remains governed solely by `profile.scheduler_enabled`. Dev stays
mock/local; production live reads stay config-gated. The readiness probe is
local-URL-only via `urllib` with a timeout (no internet). Dev/Production DB and
app-support isolation is unchanged (tests fail on path collision). No Graph/Procore
writeback, no raw bodies/payloads, no vectors — none of those surfaces are touched.

## Evidence / tests

`docs/evidence/source-refresh/` gains `dev-launcher-open-proof`,
`production-launcher-open-proof`, and `browser-mode-close-policy-proof` pairs
(generated by `scripts/proofs/launcher_scheduler_evidence_proof.py`).
`tests/test_launcher_scheduler.py` covers dev/prod `--open` opening the resolved URL,
status reporting `frontend_url`/`frontend_url_source`, readiness wait + timeout
warning, non-blocking/non-fatal browser open, browser-mode intercept flags, pywebview
lazy/optional + fallback, Dev/Prod URLs differing via config, fallback default, DB
isolation, and the shortcut helpers pointing at `launcher <env> --open`. New modules
are in strict ruff + mypy scope (`hb_assistant.launcher.*`).
