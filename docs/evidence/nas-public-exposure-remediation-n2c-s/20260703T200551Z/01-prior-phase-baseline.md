# N2C-S · 01 — Prior-Phase Baseline

Phase: **N2C-S — Public Exposure Remediation** (security remediation only) · UTC 20260703T200551Z

## Coordinates
- Branch: `audit/nas-public-exposure-remediation-n2c-s-20260703T200551Z`
- Worktree: `…/hb-personal-assistant-worktrees/audit/nas-public-exposure-remediation-n2c-s-20260703T200551Z`
- Base: `fix/nas-schema-drift-n2-20260703T151646Z` @ `4fe34348` · HEAD `4fe34348`
- Python 3.14.5 (`.venv` present) · Local start Fri Jul 3 16:05 EDT 2026

## Why this phase
N2C-R closed **FAIL** on public exposure: an operator-approved external scan (Shodan InternetDB) found
**MariaDB 3306 reachable on the WAN IP**. That is a live security risk independent of HB. N2C-S removes
public exposure for MariaDB (and reviews other NAS admin/backend/DB ports) and proves it closed.

## Carried state
- auth/security **hardened** (0700, svc-owned, write-proof PASS) — done in N2C-R.
- Port 8000 free; Tailscale Serve/Funnel OFF; memory/storage/sudoers PASS.
- **Public exposure: FAIL** (MariaDB 3306 on WAN) — the target of this phase.
- N3 copied-DB smoke and production cutover **remain prohibited**.

## Scope guardrails
Security remediation only. No DB copy/open, no HB backend/container, no copied-DB smoke, no secrets, no
vault, no schedulers/watchers. Router/DSM changes are **operator-performed**; the agent does read-only
NAS checks + external scans + provides exact checklists. No sudo executed by the agent.
