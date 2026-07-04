# N2 · 01 — Prior-Phase Baseline

Phase: **N2 — Safe DB Migration Planning + Schema Drift Audit**
Timestamp (UTC): 20260703T151646Z

## Lineage

| Phase | Scope | Result |
|---|---|---|
| N0 | NAS readiness audit | WARN / conditional pass |
| N1A | NAS remediation (Portainer stopped, port 8000 freed) | WARN |
| N1B | NAS runtime scaffold (`deploy/nas/`) | PASS |
| N1C | Bounded scratch container smoke (`/health` 200, non-root, loopback, workers off) | PASS |
| N1D | NAS security hardening + exposure confirmation | WARN (after sudoers re-verify) |
| **N2** | **Schema-drift audit + fix + safe-DB migration planning** | **this phase** |

## Carried gate status entering N2

- N1C Docker sudoers grant: **revoked / PASS**.
- Memory/swap: **PASS** (~19–20 GiB total, ~16 GiB avail, swap 0 B, after RAM upgrade).
- Port 8000: **PASS** (free for HB; Portainer remains off 8000).
- auth/security ACLs on NAS: **still 0777, not hardened** → secrets remain prohibited.
- Public exposure: **operator confirmation still pending / UNKNOWN**.
- Runtime-user / admin split (`personal-assistant-svc` in `administrators`): **still deferred**.
- **Schema drift: the active DB-migration blocker — the subject of N2.**
- Copied-DB smoke: **still prohibited**.
- Production cutover: **still prohibited**.

## What N2 is / is not

N2 is a **repo-truth audit + bounded code/test fix + planning** phase. It touches only repo files
and disposable `tmp_path` scratch SQLite DBs. It does **not**: copy/open/migrate any live or
production DB, start a backend/container, migrate secrets, write the vault, use sudo, SSH to the NAS
for anything mutating, or commit/push. See `09-risk-and-stop-conditions.md`.

## Source of the drift signal

N1C scratch `/health` (committed at
`docs/evidence/nas-scratch-smoke-n1c/20260703T132549Z/nas-artifacts/health.json`) reported
`schema_version: 98`, `schema_expected: 97`, `schema_ready: true` — the mismatch this phase resolves.
