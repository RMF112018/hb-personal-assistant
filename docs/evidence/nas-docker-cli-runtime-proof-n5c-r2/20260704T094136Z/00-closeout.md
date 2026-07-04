# N5C-R2 — Docker CLI Runtime Proof — Closeout

**Verdict: PASS.**

## Objective
Prove that the `hb-assistant` CLI runs on the NAS via the repo's intended `deploy/nas` Docker runtime
(`python:3.12-slim`), by executing help-only commands with no side effects — the prerequisite the native-venv path
(N5C-R) could not satisfy (NAS Python maxes at 3.9 < required 3.12).

## Result
| Check | Result |
|---|---|
| Docker image present | ✅ `image_preexisting=yes` (`hb-personal-assistant:nas`) — reused, no rebuild needed |
| `hb-assistant --help` | ✅ `exit_code=0` (Usage/Options printed) |
| `hb-assistant auth --help` | ✅ `exit_code=0` |
| `hb-assistant auth login --help` | ✅ `exit_code=0` (device-code options shown) |
| Container exits after each command | ✅ `--rm`; `lingering=0` |
| No backend/uvicorn container running | ✅ `running_hbpa=0` |
| Production DB unchanged | ✅ `db_pre` mtime/size == `db_post` mtime/size |
| No MSAL cache created | ✅ `auth_cache_pre=0` == `auth_cache_post=0` |
| MSAL login attempted | ✅ **No** |

## How it was kept side-effect-free
Each CLI command ran via `docker run --rm --network none hb-personal-assistant:nas <cli...>`:
- **Command overridden** → the image's default `CMD` (uvicorn backend) never ran; only the CLI help executed.
- **No `-p`/ports, no `-v`/volumes** → the container had **no access** to the NAS DB, config, or app-support tree
  (structurally impossible to open/migrate the DB or write a token cache).
- **`--network none`** → no egress during the help run.
- Image bakes `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` and runs as non-root `hbsvc` (1028:100).
- `compose up` was deliberately **not** used (it mounts app-support read/write and has a DB-touching healthcheck).

## Consequence
The NAS now has a **proven Python-3.12 CLI runtime** for `hb-assistant`. **N5C-A (MSAL device-code login) is
unblocked** for a separate authorization — see `05` for the exact command form (it will additionally need a bounded
app-support/auth bind-mount so the cache persists to the NAS with correct ownership).

## Boundaries held (see 03)
No MSAL login · no backend/uvicorn · no MCP · no watcher/scheduler · no ingestion/card generation · no DB write-open
(no DB access at all) · no production config activation · no push/PR.

## Evidence index
- `01-preflight-and-deploy-verification.md` — git preflight + Dockerfile/compose verification.
- `02-docker-cli-help-proof.md` — the three help runs + side-effect checks.
- `03-boundaries-maintained.md` — explicit non-actions.
- `04-git-status.md` — repo posture.
- `05-msal-login-command-form.md` — exact bounded command form for the later N5C-A MSAL login.
- `local-sensitive/README.md` — un-redacted host/paths (gitignored).
