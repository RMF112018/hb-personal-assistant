# N2C-S · 03 — NAS Local Listener Inventory

Read-only, as `personal-assistant-svc`. **Local listening ≠ WAN exposure** — the router/firewall is
decisive; this inventory identifies *what could be exposed if forwarded.*

## Risk-port listeners (bind address)

| Port | Service | Listening? | Bind |
|---|---|---|---|
| 22 | SSH (default) | no | — |
| **10021** | SSH (HB) | yes | 0.0.0.0 / :: |
| **443** | HTTPS / DSM / proxy | yes | 0.0.0.0 / :: |
| **5000** | DSM HTTP | yes | 0.0.0.0 / :: |
| **5001** | DSM HTTPS | yes | 0.0.0.0 / :: |
| 8000 | HB backend (future) | **no** ✅ | — |
| 9000 | Portainer | **no** ✅ | — |
| 9443 | Portainer | **no** ✅ | — |
| **3306** | **MariaDB** | **yes** ⚠️ | **0.0.0.0** |
| 2049 | NFS | yes | 0.0.0.0 / :: |
| 445 | SMB | yes | 0.0.0.0 / :: |
| 5005 | WebDAV | no | — |
| 5006 | WebDAV (SSL) | yes | :: (IPv6) |
| 8123 | Home Assistant | yes | 0.0.0.0 / :: |

## Context
- **MariaDB (3306) binds `0.0.0.0`** on the NAS. Combined with the external scan (`02`) seeing 3306 on the
  WAN, the router is almost certainly **forwarding 3306** (static rule, UPnP mapping, or DMZ) to the NAS.
- SSH is on **10021** only (22 not listening). 8000 and Portainer 9000/9443 are **not** listening (good).
- DSM (5000/5001/443), NFS (2049), SMB (445), WebDAV (5006), Home Assistant (8123) bind all-interfaces —
  normal for LAN/Tailnet, but must **not** be WAN-forwarded.
- **Current NAS LAN IP: 10.0.0.89** (the handoff's 10.0.0.58 is stale — DHCP changed). Router rules may
  target **either** IP; review forwards to the NAS by hostname/MAC, and set a DHCP reservation.
- Tailscale Serve/Funnel: **OFF** (re-confirmed). MariaDB10 package is installed (`/var/packages/MariaDB10`).

## Verdict
MariaDB listens broadly on the NAS; closing WAN exposure is a **router/firewall** action (`04`/`05`).
Optionally, MariaDB can later be bound to localhost/LAN only (package-level) — deferred, router-block first.
