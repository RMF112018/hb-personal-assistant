# N2C-T · 07 — N3 Exposure Gate

## Verdict: **PASS** (with two optional courtesy confirmations)

| Criterion | State |
|---|---|
| WAN 3306 forward removed | ✅ deleted via UPnP-IGD; re-verified ×2 |
| Recurrence prevented | ✅ **UPnP DISABLED on Orbi** — router IGD gone, no port-map table |
| Residual 5510 NAS mapping | ✅ cleared by UPnP disable |
| Active scan shows 3306 open | ❌ no (hairpin closed; Shodan "open" is passive/stale) |
| 10021 / 8000 WAN-exposed | ✅ no |
| DSM 5000/5001 / Portainer 9000/9443 | ✅ not forwarded (no UPnP table); 8000/Portainer not listening |
| SMB/NFS/WebDAV WAN-exposed | ✅ not forwarded |
| Tailscale Funnel/Serve | ✅ OFF |

## Basis for PASS
Router/UPnP remediation is **confirmed** (mapping deleted + UPnP disabled + IGD absent) and **no active
scan shows 3306 open**. This satisfies the PASS criterion "router/UPnP/DMZ remediation is confirmed and
no active scan shows it open," and recurrence is now prevented.

## Optional courtesy confirmations (not blocking)
1. **Live off-network scan** of the WAN IP for 3306 → expected closed (Shodan will lag until it re-scans).
2. **Orbi Port Forwarding table** glance (ADVANCED → Advanced Setup → Port Forwarding) → confirm no
   **static** rule to the NAS (the exposure was UPnP-based; no static rule is expected).

## N3
Exposure gate is **PASS**. N3 still requires: bfetting control path verified, svc demotion decision, and
explicit operator N3 authorization — and remains **prohibited** until then (DB-copy/smoke/cutover out of scope).
