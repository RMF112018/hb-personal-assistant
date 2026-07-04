# N5C-R — NAS CLI Runtime Proof — Closeout

**Verdict: BLOCKED** (the native-venv CLI runtime proof cannot pass on this NAS; the CLI runtime is container-only).
**No venv created. No runtime installed. No login run. Nothing written to the NAS. Boundaries fully held.**

## Objective
Establish a runnable `hb-assistant` CLI on the NAS (using the user-authorized N4C repo checkout) and prove
`hb-assistant --help` / `auth --help` / `auth login --help`, as a prerequisite before the N5C-A MSAL device-code login.

## Result
1. **N4C repo checkout: structurally VALID** (read-only inspection, `01`).
   - `src/hb_assistant/`, `cli/main.py`, `cli/auth.py`, `pyproject.toml`, `config/config.example.yml` all present.
   - Console script `hb-assistant = "hb_assistant.cli.main:cli"`.
   - No venv present (clean). No `.git` (a source export, not a clone → no commit/branch).
   - No `hb-assistant`/`uvicorn`/MCP/scheduler/Python-watcher process running (the only `watchdog` hits are kernel
     `[watchdog/N]` kthreads, PID 2 children — unrelated).
2. **Runtime capability: BLOCKED** (`02`).
   - The package requires `requires-python = ">=3.12"`.
   - The NAS provides **only Python 3.8.15 (system) and Python 3.9 (Synology Package Center)** — **no 3.11/3.12/3.13**
     anywhere on PATH or in common locations. A venv built from 3.8/3.9 **cannot** install a `>=3.12` package.
   - The repo's intended runtime is **containerized**: `deploy/nas/Dockerfile` is `FROM python:3.12-slim`, and
     `deploy/nas/compose.yaml` uses `image: hb-personal-assistant:nas`. Docker/ContainerManager is installed
     (`/usr/local/bin/docker`).

## Why BLOCKED (not FAIL/PASS)
The auth mechanism and repo are sound; the CLI simply has no compatible **native** interpreter on this host, and the
only viable runtime (Docker python:3.12) is an explicit hard boundary in N5C-A/N5C-R that I will not cross without
separate authorization. This is a precondition gap, not a defect.

## Consequence
**N5C-A (MSAL device-code login) remains BLOCKED** — it cannot run until a Python-3.12+ CLI runtime exists on the NAS
(container or otherwise). See `05` for options.

## Boundaries held (see 03)
No venv created · no pip install · no Docker started · no backend/MCP/scheduler/watcher · no source ingestion/card gen
· no DB opened · no config activated · no MSAL login · no NAS writes · no push/PR.

## Evidence index
- `01-n4c-repo-inspection.md` — read-only structural verification of the N4C checkout.
- `02-runtime-capability-audit.md` — Python-version blocker + intended container runtime.
- `03-boundaries-maintained.md` — explicit non-actions.
- `04-git-status.md` — repo/branch posture.
- `05-next-step-options.md` — options + recommendation to unblock.
- `local-sensitive/README.md` — un-redacted host/paths (gitignored).
