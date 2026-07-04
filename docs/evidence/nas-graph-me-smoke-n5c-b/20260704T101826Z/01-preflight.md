# 01 — Preflight

## Git / phase state
- Branch: `ops/nas-copied-db-n3-20260704T060648Z`, HEAD `cbf2cea6` (`docs(nas): add N5C-A MSAL Graph auth proof`).
- Working tree clean, 15 ahead / 0 behind, local branch only (never pushed).
- **N5C-A committed locally at `cbf2cea6`** (11 evidence files tracked) — precondition satisfied.

## Phase boundary statement
N5C-B is a **bounded Graph `/me` smoke** proving token-cache usability + Graph connectivity only. It is **not** source
ingestion, mail/calendar/file access, backend runtime, MCP, scheduler/watcher, Cloudflare, or any scope/config change.
Kept **separate** from N5C-A (auth-cache proof) as its own phase/evidence package.

## Runtime
- Image: `hb-personal-assistant:nas` (python:3.12-slim; from N5C-R2, reused).
- Execution via operator interactive sudo (Docker socket is root-owned). One-shot `docker run --rm`, not compose.
