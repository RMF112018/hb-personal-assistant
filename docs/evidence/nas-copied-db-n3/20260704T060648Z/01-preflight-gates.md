# 01 — Preflight Gates (N3)

Timestamp: 20260704T060648Z
Worktree: `ops/nas-copied-db-n3-20260704T060648Z` @ HEAD `9e533f6a`
Base branch: `audit/nas-public-exposure-remediation-n2c-s-20260703T200551Z` @ `9e533f6a`

## Inherited N2/N2C gate state (from committed evidence)

N2C evidence is **committed** on the base branch in commit `9e533f6a` ("docs(nas): add N2C gate closeout evidence", docs-only, clean tree). The operator's preferred precondition (evidence committed before N3) is **satisfied** — no operator stop required at Step 2.

| Gate | Source phase | State |
|---|---|---|
| auth/security hardening | N2C-U/V | PASS (per committed closeout) |
| public exposure remediation (3306 removed) | N2C-S | PASS |
| UPnP recurrence prevention | N2C-S/V | PASS |
| DSM firewall (default-drop + LAN/Tailnet allow) | N2C-U | PASS |
| bfetting SSH + sudo | N2C-U/V | PASS *(see access note below)* |
| personal-assistant-svc demotion | N2C-U/V | PASS |
| runtime folder access after demotion (9 folders) | N2C-U | PASS |
| port 8000 free / not listening | N2C-V | PASS |
| no DB copy yet performed | N0–N2C | PASS (N3 is first copy) |

Reference committed evidence dirs on this branch:
`docs/evidence/nas-safe-db-migration-n2/`, `.../nas-scaffold-test-hardening-n2b/`,
`.../nas-public-exposure-remediation-n2c-s|-t/`, `.../nas-firewall-defense-n2c-u/`,
`.../nas-gate-closeout-n2c-final/20260704T054834Z/`.

## Schema constant

`src/hb_assistant/store/migrator.py:17` → `LATEST_SCHEMA_VERSION = 98` on this branch (aligned in `b912b4ed`). Live-DB and copy applied head both read **98** via `SQLiteMigrator(db).current_version()`.

## Disk headroom (Mac side)

`/System/Volumes/Data` (holds both the live DB and the scratchpad staging dir): 142 GiB available. A 3.9 GiB copy fits with wide headroom. **PASS.**

## Disk headroom (NAS `/volume1`)

**NOT CAPTURED** — blocked. See access note.

## Access note — bfetting SSH blocked (non-interactive)

`ssh -p 10021 bfetting@<nas-tailnet>` returns `Permission denied (publickey,password)` under `BatchMode`. The local key `~/.ssh/id_ed25519` (`SHA256:MVNxD9x0mf6QEdwIb4XxOGmZV4mH4Z/uaVMfIZ/4YAE`) is not in bfetting's `authorized_keys`; the NAS host key is trusted in `known_hosts` (prior sessions connected). bfetting authenticates by **password**, which cannot be supplied non-interactively and which this agent does not handle.

Consequence: local Steps 1–4 + schema validation completed; **NAS placement (Step 5), service-user validation (Step 6), hash equivalence (Step 7), and NAS boundary re-check (Step 8-NAS) are blocked pending operator provisioning of bfetting access** (add the above key to `authorized_keys`, or operator runs the NAS commands).

## Git state

Branch 4 commits ahead of origin/main (`9e533f6a`, `4fe34348`, `b912b4ed`, `581ad598`). Working tree clean at worktree creation. Full capture in `10-git-status.md`.
