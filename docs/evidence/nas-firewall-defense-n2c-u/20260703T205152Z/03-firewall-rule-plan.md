# N2C-U · 03 — DSM Firewall Rule Plan (to apply)

Goal: NAS services reachable only from **trusted LAN + Tailnet**; all other inbound denied.
**Allow-before-deny ordering is mandatory** (see `01` — the agent's SSH is tailnet-sourced).

## DSM path
Control Panel → Security → **Firewall** → **Enable firewall** → Edit Rules (profile: default, or create
`hb-lan-tailnet-only`).

## Rules (create in THIS order — top to bottom)
| # | Action | Source IP | Ports | Protocol | Notes |
|---|---|---|---|---|---|
| 1 | **Allow** | **10.0.0.0/24** (LAN) | All | All | trusted LAN |
| 2 | **Allow** | **100.64.0.0/10** (Tailnet) | All | All | trusted Tailscale — **keeps agent SSH alive** |
| 3 | **Deny** | All / 0.0.0.0/0 | All | All | default-deny (must be **below** 1 & 2) |

On Synology, if you enable the firewall and add only rules 1 & 2, there is an **implicit deny** for
everything else — rule 3 is then optional. Either approach is fine; rule order must keep the two Allows
**above** any Deny.

### Interface note
Apply the rules to the **LAN interface** (and "All interfaces" if offered). If a separate **Tailscale**
interface is listed, ensure it is either allowed or not firewalled. If DSM does **not** list the
Tailscale tun interface, tailnet traffic is unfiltered (agent SSH safe regardless) — the Tailnet allow
rule is still recommended for correctness.

### If default-deny is not cleanly available
Add targeted **Deny (source: all)** rules for these ports (still below the two Allows):
`22, 10021, 3306, 5510, 6690, 5000, 5001, 8000, 9000, 9443, 445, 139, 111, 2049, 5005, 5006, 8123`.

## Lockout safety (operator, before clicking Apply)
1. Keep a **DSM session open from a LAN device** (e.g., the Mac at 10.0.0.79 → `https://10.0.0.89:5001`)
   so you can revert if access breaks.
2. Verify rules 1 & 2 (Allow LAN, Allow Tailnet) are **above** any Deny.
3. Apply.
4. Tell the agent — it will immediately verify SSH over **both** tailnet (100.66.28.14) and LAN
   (10.0.0.89) still work. If broken, do **not** close your DSM session; delete the Deny rule to revert.
