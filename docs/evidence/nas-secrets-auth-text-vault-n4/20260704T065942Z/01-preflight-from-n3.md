# 01 — Preflight from N3

## Git state (matches expected N3)
| Field | Value |
|---|---|
| branch | `ops/nas-copied-db-n3-20260704T060648Z` |
| HEAD | `761864ea` (expected `761864ea`) ✔ |
| vs origin/main | 0 behind / **5 ahead** |
| working tree | clean |
| push status | **not pushed**; no PR |

Commit stack (5 ahead): `761864ea` N3 evidence · `9e533f6a` N2C evidence · `4fe34348` N2B scaffold-test · `b912b4ed` schema 97→98 · `581ad598` NAS scaffold.

## N3 result re-confirmed
N3 = PASS. Copied v98 DB placed at the NAS intended path, owner `personal-assistant-svc:users`, mode 600;
service-user RO validation passed (`quick_check=ok`, `integrity=ok`, schema=98, table_count=506). Evidence:
`docs/evidence/nas-copied-db-n3/20260704T060648Z/` (committed in `761864ea`).

## Local copy ↔ NAS DB linkage (basis for reading refs from the local copy)
The encrypted-reference audit in this phase reads the **sha-verified local copy** in the session scratchpad
(read-only), NOT the NAS DB — because opening the NAS copy writably would auto-migrate it (see 09 / `apply()` gate).
Linkage proof:
- N3 proved the local copy and the NAS-placed file are **byte-identical** (equal SHA-256; recorded in this phase's
  `local-sensitive/` and in N3 `local-sensitive/`).
- This phase re-verified the local copy's SHA-256 is **unchanged** from the N3-recorded value ✔.
- NAS DB metadata re-checked read-only **now**: `size = 4,151,631,872` (unchanged), main-file `mtime` = the N3
  placement time (unchanged), owner `personal-assistant-svc:users`, mode 600. The `-wal` (0 B) / `-shm` sidecars
  present are read-open artifacts from the operator's N3 svc validation; the main DB was not mutated (mtime/size
  unchanged). A full NAS re-hash now requires sudo (file is `svc:600`) and is deferred; metadata + the unchanged
  local-copy SHA together establish the local copy faithfully represents the NAS DB content.

⇒ Reference counts derived from the local copy apply equally to the NAS DB.

## N3-precondition gates (still hold)
auth/security hardened (700 svc); exposure closed; DSM firewall enabled; bfetting control path (key-agent SSH);
svc demoted; port 8000 free; sudo password-gated (no NOPASSWD).
