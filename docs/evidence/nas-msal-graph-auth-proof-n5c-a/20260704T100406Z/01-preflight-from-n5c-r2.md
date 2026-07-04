# 01 — Preflight (from N5C-R2)

## Git posture at N5C-A start
- Branch `ops/nas-copied-db-n3-20260704T060648Z`, HEAD `a36b3e68` (`docs(nas): add N5C-R2 Docker CLI runtime proof`),
  clean, 14 ahead / 0 behind, local branch only (never pushed).
- Prior evidence committed: N5C (11), N5C-R (6), N5C-R2 (6) — all tracked. No uncommitted prior evidence.

## Prerequisite verdicts
- **N5C-R2 = PASS** — Docker CLI runtime proven (`hb-personal-assistant:nas`, python:3.12-slim); `hb-assistant --help`
  / `auth --help` / `auth login --help` all exit 0, side-effect-free; MSAL login not attempted there.
- **N5C-R = BLOCKED** (native venv infeasible; NAS Python max 3.9 < required 3.12) — superseded by the Docker runtime.
- **N5C = PASS** (consolidation; auth planned). Recommended command form recorded in N5C-R2 `05`.

## Execution model
- Docker requires sudo on the NAS (root-owned socket); the operator ran all container commands via interactive,
  password-gated sudo. The agent designed the bounded blocks and interpreted redacted results.
- Login ran inside the container as `--user 1028:100` (= `personal-assistant-svc:users`), so the cache is owned by the
  runtime service user.
