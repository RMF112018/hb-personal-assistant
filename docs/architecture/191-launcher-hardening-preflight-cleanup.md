# 191 — Launcher Hardening: Preflight, Port Determinism & Stale Cleanup

**Objective:** make `hb-assistant launcher dev|production --open --json` clean
enough to wrap in an Automator/Dock shortcut. Dev validation surfaced five
defects: backend `[Errno 48] address already in use` on 8000; Vite drifting
5173→5175 while the launcher still reported/opened 5173; child `vite`/`uvicorn`
output bleeding into the caller's terminal after the JSON; and `close --action
quit` leaving stale prior-session uvicorn/npm/vite/scheduler processes alive
(it only terminated the *current* tracked session). Builds on
[188](188-launcher-open-frontend.md).

## Preflight (`launcher/preflight.py`)

`run_preflight(profile, manager, *, force_restart, required_ports)` runs before a
non-plan spawn:

1. Reconcile the tracked session. If the key port-binding surfaces
   (`backend`, `frontend`) are **alive** and not `--force-restart` → `reused=True`
   and the caller skips spawning (no duplicate processes).
2. Otherwise stop an unhealthy/partial prior session (`stopped_prior`).
3. For each required port in use, resolve listener PIDs and classify each:
   - launcher-owned (tracked PID or signature) → terminate, record in
     `freed_ports`;
   - unknown owner (or an unidentifiable listener) → record in `conflicts` and set
     `ok=False`.

When `ok=False` the launcher **fails closed**: `status="port_conflict"`,
`port_conflicts` listed, **no** conflicting process spawned, CLI exits 2. This is
the chosen policy for an unknown holder of a required port.

## Port determinism

- `Profile` now carries `backend_port` (config `launcher.<env>.backend_port`,
  default 8000) and `frontend_port` (parsed from `frontend_url`).
- Dev frontend spec is `npm run dev -- --port <frontend_port> --strictPort --host
  127.0.0.1`: Vite binds exactly that port or exits — **no 5173→5175 drift**, so
  the reported/opened `frontend_url` always matches the served port.
- Production static server binds `frontend_port` via `http.server`.
- Backend uvicorn binds `--port <backend_port>`.
Preflight frees launcher-owned stale holders of these ports; unknown holders fail
closed; so the served ports are deterministic.

## Subprocess output isolation (`process_manager.spawn`)

`spawn` now redirects child `stdout`/`stderr` to a per-environment log file
(`<app_support>/logs/launcher/<env>-<name>.log`, append) and `stdin` to DEVNULL;
the parent file handle is closed after `Popen` (the child keeps its dup'd fd). The
`ProcessRecord` records `log_path` and `port`. Result: no managed-process output
reaches the caller's terminal / Automator stdout after the JSON is emitted —
`--json` is clean and parseable.

## Process discovery (`launcher/process_scan.py`)

No `psutil` dependency. `ps -axww` enumerates processes, a stdlib `socket` probe
tests port occupancy, and `lsof` resolves listener PIDs (all best-effort,
monkeypatchable). `classify` returns a launcher role only for **env-attributable**
signatures:
- `scheduler` — `daily-source-refresh` + `--environment <env>`;
- `frontend` — (`vite`|`http.server`) + `/frontend` + the env's frontend port;
- `backend` — the analytics-API module + the backend port.

`classify` **never** returns `mcp`: `second-brain mcp serve --stdio` is also what
Claude/Cursor launch, so a launcher MCP is only ever terminated via a recorded
session PID — never by signature. This keeps cleanup/quit from killing unrelated
IDE MCP processes.

## Cleanup (`launcher cleanup --environment <env> [--apply]`)

Dry-run by default: lists candidates (live tracked-session PIDs of any role,
including a *tracked* MCP, plus signature-matched stale scheduler/frontend/backend)
and `skipped_unknown` (unknown holders of the required ports). `--apply`
terminates the candidates and reports `terminated` / `still_running`. A foreign
(untracked) MCP is never a candidate.

## Quit semantics (`close_policy.apply("quit")`)

Quit terminates the current tracked session, then sweeps signature-matched stale
launcher processes (MCP excluded). The receipt gains
`terminated_current_session`, `terminated_stale`, `skipped_unknown`, and
`still_running` (existing `terminated`/`kept_alive` keys preserved). Background is
unchanged (the four new keys default empty).

## MCP lifecycle (v1.3.1)

stdio MCP (`second-brain mcp serve --stdio`) is launched on demand by the IDE
client (Claude/Cursor) and exits without an attached client — it is **not** a
persistent launcher-owned background service. So when `profile.mcp_mode ==
"stdio"` (today's only mode) the launcher:

- does not build an MCP spec → never spawns it and never records it in the
  session's managed processes (so it is never marked failed/exited);
- reports it as externally managed in `status()` / `--open`:
  `mcp_status="external_client_managed"`, `mcp_mode="stdio"`,
  `mcp_managed_by_launcher=false`,
  `mcp_reason="stdio MCP is launched by Claude/Cursor and is not a persistent
  browser-launcher process"`.

Because stdio MCP is never a managed record and `process_scan.classify` never
matches the MCP signature, `close`/`quit`/`background`/`cleanup` never terminate an
external IDE MCP. A future non-stdio transport may be launcher-managed only when
explicitly configured (`mcp_mode != "stdio"`), in which case the MCP spec is built
and reported via the normal managed path. Claude/Cursor MCP launcher scripts are
untouched.

## Guardrails

Dev/Production isolation unchanged (per-environment session/DB/app-support;
preflight and cleanup are env-scoped). No live reads / source refresh /
Graph/Procore writeback added. Cleanup and quit never kill unrelated Claude/Cursor
MCP processes (MCP only via tracked PIDs). The port-occupancy probe is a local
socket connect; `lsof`/`ps` are best-effort and degrade to empty.

## Evidence / tests

`docs/evidence/source-refresh/` gains `launcher-preflight-proof` (free-stale vs
fail-closed), `launcher-cleanup-proof` (dry-run; foreign MCP safe), and
`launcher-quit-stale-proof` (current + stale sweep). `tests/test_launcher_scheduler.py`
adds: preflight frees launcher-owned ports; unknown port → `port_conflict` exit 2;
healthy-session reuse vs `--force-restart`; dev frontend spec carries
`--strictPort`+`--port`; `spawn` redirects to a log file (DEVNULL stdin); clean
JSON output; quit sweeps stale; cleanup skips foreign MCP and sweeps a tracked MCP.
An autouse fixture stubs OS scanning so the suite is hermetic and never touches the
host. New modules are in strict ruff + mypy scope.
