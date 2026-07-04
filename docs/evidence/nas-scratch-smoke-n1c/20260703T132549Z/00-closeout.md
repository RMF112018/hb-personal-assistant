# 00 — N1C Closeout

**Phase:** N1C — Bounded Scratch Container Smoke Test. **Result: PASS.**
**Run (UTC):** build 2026-07-03T14:27:42Z · run 2026-07-03T14:28:19Z→14:28:37Z

## Run identity
| Item | Value |
|---|---|
| Worktree | `feature/nas-runtime-scaffold-n1b-20260703T123726Z` |
| N1B commit (base) | `52d3d419` (`feat(nas): add runtime scaffold for backend deployment`) |
| N1C scaffold fixes | **uncommitted** — `deploy/nas/Dockerfile`, `.dockerignore` (see `02`) |
| NAS | `<nas-hostname>` `<nas-tailnet-ip>` (tailnet), SSH :`<nas-ssh-port>`, user `personal-assistant-svc` |
| Image | `hb-personal-assistant:nas` — 263MB — id `144ac90ca3d7` (base `python:3.12-slim`) |
| Evidence artifacts | `nas-artifacts/{build.log,container.log,health.json,run-transcript.log}` |

## Outcome
The HB backend container **built, booted as non-root (`hbsvc` uid 1028), served `/health` (HTTP 200)
in ~9s, and stopped/removed cleanly** — against a **disposable scratch app-support root only**. No live
DB, copied DB, secrets, vault, or source-roots were involved. Loopback-only publish confirmed. Background
workers/watchers/schedulers confirmed disabled. Live app-support was untouched (0 files before, during, after).

## Requirements — all 12 proven (detail in `01`)
Scratch paths/config ✓ · image build ✓ · loopback `127.0.0.1:8000` start ✓ ·
`HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` ✓ · NAS-local `/health` 200 ✓ · logs captured ✓ ·
live app-support untouched (0→0) ✓ · stop/down ✓ · port 8000 free after ✓ · evidence captured ✓ ·
no Portainer/unrelated-container/firewall changes ✓.

## Two scaffold defects found & fixed during the smoke (see `02`)
1. **Non-root user couldn't read the source tree** — first boot failed `ModuleNotFoundError: hb_assistant`.
   `COPY` preserved restrictive POSIX modes (0700 `src/`) from the ACL-backed share. **Fix:** `RUN chmod -R
   a+rX /app` in the Dockerfile (read+traverse only).
2. **`.dockerignore` stripped real source packages** — `**/auth/` and `**/security/` (meant for the runtime
   *app-support* secret trees) also matched `src/hb_assistant/{auth,security}/`, breaking import. **Fix:**
   narrow to secret *files* only; those source packages carry no secrets (runtime secrets live under
   app-support, never in the build context).

Both are genuine robustness fixes for the image (also add macOS AppleDouble excludes + defensive `**/.env*`).

## Boundaries honored
No live DB copy/open, no copied DB, no secrets/tokens/MSAL/Procore, no Text Vault, no live vault, no
source-roots, no schedulers/watchers, no `0.0.0.0` publish, no Portainer restart, no unrelated container
changes, no firewall/router/Tailscale changes, no push, no PR. Interactive-sudo/NOPASSWD-docker only.

## Standing changes to be aware of (see `03`)
- **NOPASSWD sudo drop-in** `/etc/sudoers.d/hb-n1c-docker` (docker-only) — **you must revoke it** (command in `03`).
- **Retained inert artifacts:** image `hb-personal-assistant:nas` + `config/hb-pa-config.smoke.yml` (removal commands in `03`).
- **Removed:** `app-support-smoke` (scratch DB), `_n1c_build` (build context), `_n1c_evidence` (pulled here).

## Result: **PASS** — container runtime proven on the NAS against scratch only.
Per scope: **STOP here.** Do NOT proceed to copied-DB smoke, credential migration, or cutover without separate authorization.
