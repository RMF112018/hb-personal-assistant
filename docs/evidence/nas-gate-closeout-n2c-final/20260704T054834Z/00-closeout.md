# N2C-V — NAS Gate Closeout + N3 Readiness (FINAL)

- **Phase:** N2C-V (consolidated closeout of the N2C-S/T/U remediation stack)
- **Timestamp (UTC):** 20260704T054834Z
- **Worktree:** `audit/nas-public-exposure-remediation-n2c-s-20260703T200551Z`
- **HEAD:** `4fe34348` (N2B) — nothing committed for N2C-S/T/U/V (evidence-only, uncommitted)
- **Verdict:** **PASS — all N2 security/technical gates closed. N3 is READY FOR EXPLICIT OPERATOR AUTHORIZATION (not proceeding).**

## What this phase does
Consolidates the machine proof and operator-provided proof from the three remediation
sub-phases into one authoritative gate matrix and an N3 go/no-go verdict:

- **N2C-S/T** — public WAN exposure (mistaken "MariaDB 3306") traced to a **Synology UPnP
  port-map** (WAN 3306/TCP → `10.0.0.58:6690`, Synology Drive) and removed via credential-free
  UPnP-IGD `DeletePortMapping`; operator then **disabled UPnP** on the Orbi router.
- **N2C-U** — DSM firewall enabled with allow-LAN + allow-Tailnet + **default deny-all**;
  applied by the operator through a lockout-safe SSH-tunnel-to-localhost path.
- **Service-user demotion** — `personal-assistant-svc` removed from `administrators`
  (least-privilege runtime); `bfetting` retained as the admin control path.

## Agent-side corroboration captured THIS phase (read-only, no NAS writes)
1. `ssh -p 10021 personal-assistant-svc@<nas-tailnet> id` → **Permission denied**
   (confirms svc SSH is disabled post-demotion — my own observation, not just operator report).
2. UPnP-IGD re-enumeration against the Orbi (`10.0.0.1`) → **"NO WANIPConnection/WANPPPConnection
   control URL found via UPnP"** (confirms UPnP recurrence-prevention holds; no gateway to re-add a map).

## Gate summary (detail in `01-gate-matrix.md`)
| Gate | Result |
|---|---|
| Schema drift (N2) | PASS |
| Scaffold test drift (N2B) | PASS |
| Auth/security ACL hardening | PASS (operator proof) |
| Public WAN exposure removed | PASS (router-table proof + agent re-enum + UPnP disabled) |
| DSM firewall defense-in-depth | PASS (machine proof: `synofirewall` export) |
| bfetting admin control path | PASS (operator proof + agent svc-denied corroboration) |
| Service-user least-privilege | PASS (operator proof) |
| Port 8000 posture | PASS-with-note (loopback/LAN only; no public map; firewall deny-all covers) |
| **DB copy / secrets / backend / N3** | **NOT RUN — prohibited until authorized** |

## Boundaries maintained (full list in `08-boundaries-maintained.md`)
No live/copied DB touched, opened, or migrated. No secrets/keys/token-caches copied or read.
No backend/container started. No copied-DB smoke. No live vault/source-root mounted. No sudo run
by the agent. No router/firewall/Tailscale change made by the agent this phase (read-only only).
WAN IP masked as `98.x.x.183` in all committed evidence; full value only in gitignored
`local-sensitive/`. **Nothing committed or pushed.**

## Next
N3 (bounded copied-DB creation via the SQLite backup API) **may be authorized separately by the
operator.** This phase does **not** proceed to N3.
