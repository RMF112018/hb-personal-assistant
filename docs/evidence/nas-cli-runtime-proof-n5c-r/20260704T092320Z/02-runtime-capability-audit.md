# 02 — Runtime Capability Audit (the blocker)

## Requirement vs availability
| | Value |
|---|---|
| Package requirement | `requires-python = ">=3.12"` (N4C `pyproject.toml:10`) |
| NAS system `python3` | **3.8.15** |
| Synology Package Center | **Python 3.9** (`/var/packages/Python3.9`, `/usr/local/bin/python3.9`) |
| Python 3.11 / 3.12 / 3.13 | **none found** (PATH, `/usr/local/bin`, `/opt`, `/var/packages`, conda/miniconda) |
| `venv` / `ensurepip` modules | available (on 3.8) |
| PyPI reachability | reachable (`status 200`) |

**A venv created from Python 3.8 or 3.9 cannot install a `>=3.12` package** — `pip install -e .` refuses with a
Python-version mismatch. There is no compatible native interpreter on this host, so the native-venv CLI proof the
runbook specified **cannot be produced**.

## Intended runtime is containerized (repo truth)
- `deploy/nas/Dockerfile:12` → `FROM python:3.12-slim AS base`.
- `deploy/nas/compose.yaml:19` → `image: hb-personal-assistant:nas`.
- Docker is installed: `/usr/local/bin/docker` → `ContainerManager` (`docker` binary present, not on bfetting PATH).

So the repo is designed to run the backend/CLI **inside a `python:3.12-slim` container**, not as a native venv. The
"n4c-backend-smoke" naming is consistent with a container-based backend smoke.

## Implication
- The CLI runtime proof (and therefore the N5C-A MSAL login) requires a **Python 3.12+ runtime**, which on this NAS
  means either:
  1. a **Docker** container (the repo's intended path; currently an explicit hard boundary), or
  2. installing/obtaining a **native Python 3.12+** interpreter (Synology package if available, `pyenv`, or a
     portable standalone build) — a runtime-provisioning step beyond this bounded proof.
- Neither is authorized under the current N5C-R/N5C-A scope. See `05` for the decision.

## Safety note
All checks here were read-only: `python3 --version`, module-import probes, a single HTTPS HEAD to PyPI, and file
reads of `pyproject.toml`/`Dockerfile`/`compose.yaml`. No venv was created, no package installed, no container run.
