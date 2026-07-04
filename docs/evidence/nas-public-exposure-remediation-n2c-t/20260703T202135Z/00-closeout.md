# N2C-T — Closeout · SSH-Tunnel Public Exposure Remediation

UTC 20260703T202135Z · Local Fri Jul 3 16:21 EDT 2026

## Coordinates
- Branch: `audit/nas-public-exposure-remediation-n2c-s-20260703T200551Z` (continued) · HEAD `4fe34348`
- Worktree: `…/audit/nas-public-exposure-remediation-n2c-s-20260703T200551Z`
- Evidence: `docs/evidence/nas-public-exposure-remediation-n2c-t/20260703T202135Z/` (00–08 + local-sensitive)

## What happened
- **Before:** Shodan reports WAN **3306 OPEN**; NAS 3306 binds 0.0.0.0; no `upnpc` tool available.
- **Tunnel:** SSH local-forward Mac→NAS→router/DSM established (NAS allows TCP forwarding); DSM reachable
  (200); router = **NETGEAR Orbi**. Mac is also on-LAN. **Tunnel closed at end (no stale process).**
- **Root cause (via keyless UPnP-IGD enumeration):** WAN `3306/TCP` was a **Synology-created UPnP
  mapping** → NAS Synology Drive port **6690** (desc `upnpclient:6690`, targeting old IP 10.0.0.58) — not
  MariaDB, not a static rule.
- **Fix:** `DeletePortMapping(3306/TCP)` → HTTP 200; re-enumerated ×2 → **3306 mapping GONE**
  (authoritative router-table proof). Hairpin corroborates 3306 not connectable.
- **Left intact:** two Tailscale NAT-PMP UDP mappings (benign). **Flagged:** residual `5510/TCP → NAS`
  (Synology, outside 3306 authorization — recommend removal).

## Results
- **MariaDB/3306 WAN exposure: CLOSED** at the router (UPnP mapping deleted + verified).
- **Shodan still lists 3306** — passive/stale; will clear on Shodan's next scan. Live off-network scan
  recommended for final confirmation.
- **Tailscale Serve/Funnel:** OFF. **8000 / Portainer:** not listening/forwarded.
- **N2C-T result: PASS** — 3306 UPnP mapping deleted AND **operator disabled UPnP on the Orbi**
  (verified: router IGD gone, no port-map table). Recurrence prevented; residual 5510 also cleared.
  Optional courtesy checks remain (live off-network scan; Orbi static port-forward glance).

## Boundaries maintained
No DB copied/opened/migrated; no secrets/MSAL/Procore/Fernet/Text-Vault; no vault; no HB backend/container;
no Portainer restart; no schedulers/watchers. **No sudo executed.** Only change made: deleted the WAN
3306 UPnP mapping via UPnP-IGD (no credentials). No DSM/router-UI login performed by the agent. WAN IP
kept out of committed evidence (masked). Tunnel closed. **Nothing committed, nothing pushed.**

## N3
Remains **prohibited** (exposure gate WARN; DB-copy/smoke/cutover all still out of scope).

## Optional courtesy follow-ups (gate already PASS)
1. (Done) UPnP disabled on Orbi — verified.
2. Optional: live off-network scan of WAN IP confirming 3306 closed (Shodan lags).
3. Optional: glance at Orbi Port Forwarding table (confirm no static NAS rule); enable DSM firewall.
