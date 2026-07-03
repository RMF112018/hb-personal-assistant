# 01 — Repo Baseline (N1B)

**Phase:** N1B — NAS Runtime Scaffold Authoring (code/config/docs + local static validation only).
**Generated (UTC):** 2026-07-03T12:37Z · **Local:** 2026-07-03 08:37 EDT

| Item | Value |
|---|---|
| Branch | `feature/nas-runtime-scaffold-n1b-20260703T123726Z` |
| Worktree | `/Users/bobbyfetting/hb-personal-assistant-worktrees/feature/nas-runtime-scaffold-n1b-20260703T123726Z` |
| Base commit (origin/main) | `d54f07ddbe83a4973a7fd1f012c6f36fb167858a` |
| HEAD | `d54f07ddbe83a4973a7fd1f012c6f36fb167858a` (== base) |
| Python (Mac PATH) | 3.14.5 (venv not activated; validation used the repo venv for pytest) |
| Evidence dir | `docs/evidence/nas-runtime-scaffold-n1b/20260703T123726Z/` |

## Carry-forward from N0 / N1A
- **Port 8000 is now reserved for HB** — Portainer CE (`portainer-ce`) was stopped in N1A and its restart policy set `no`. Portainer must **not** be restarted on 8000.
- `/volume1/personal-assistant` exists, is **NAS-local**; `app-support/db/backups` exists; Container Manager + Docker 24.0.2 active.
- **Deferred blockers (unchanged):** auth/security folder permissions still 0777 + broad ACL (unsafe for secrets); public WAN exposure still needs operator confirmation; memory marginal (N1A freed ~300 MB → available ~1.9 GiB); runtime-user demotion unresolved.
- **Prohibited (unchanged):** DB copy/cutover, secrets copy, vault writes, background workers/schedulers/watchers.
- **Scaffold can proceed** without secrets or a live DB — this phase produces code/config/docs + static validation only.

## Prior evidence
- N0: `docs/evidence/nas-readiness-n0/20260703T113900Z/`
- N1A: `docs/evidence/nas-remediation-n1a/20260703T115417Z/`
