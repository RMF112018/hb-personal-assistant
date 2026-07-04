# 01 — N4C Repo Checkout Inspection (read-only)

User-authorized artifact: `<nas>/runtime/n4c-backend-smoke-<ts>/repo` (operator-created, confirmed safe for
inspection). All checks read-only; nothing modified.

## Structural verification
| Check | Result |
|---|---|
| repo path exists | ✅ `repo_exists=yes` |
| `pyproject.toml` | ✅ present |
| `src/hb_assistant/` | ✅ present |
| `src/hb_assistant/cli/main.py` | ✅ present |
| `src/hb_assistant/cli/auth.py` | ✅ present |
| `config/` | ✅ `config.example.yml` |
| console script | ✅ `hb-assistant = "hb_assistant.cli.main:cli"` (pyproject `[project.scripts]`) |
| venv present | ✅ **none** (`.venv` absent; no `pyvenv.cfg`/`activate`) — clean |
| `.git` metadata | ⚠️ **absent** — this is a source export, not a git clone → no commit/branch/status available |
| deploy artifacts | ✅ `deploy/nas/{Dockerfile,compose.yaml,hb-pa-config.nas.example.yml,hb-pa-config.smoke.example.yml}` |

## Running-process check (no runtime active)
`ps -ef | grep -iE 'hb.assistant|uvicorn|obsidian_mcp|scheduler|watchdog'` returned only kernel `[watchdog/0..3]`
threads (children of PID 2 `kthreadd`) — these are Linux per-CPU soft-lockup watchdog kthreads, **not** the Python
`watchdog` file-watcher. **No** `hb-assistant`, `uvicorn`, MCP, scheduler, or Python-watcher process is running from
the N4C repo.

## Assessment
The checkout is a **structurally valid** source tree with the CLI package and console-script declaration intact, no
venv, and no active runtime. It is suitable as a code source; the blocker is the interpreter version (`02`), not the
repo contents. The missing `.git` is expected for an export and does not affect a CLI runtime.
