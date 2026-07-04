# N2C-T · 03 — UPnP Check + Remediation (ROOT CAUSE + FIX)

No `upnpc` binary on Mac/NAS, so a small read-only Python UPnP-IGD client was used (SSDP discover →
WANIPConnection control URL `http://10.0.0.1:5000/ctl/IPConn` → `GetGenericPortMappingEntry`). UPnP-IGD
requires **no authentication** — enumeration and the single deletion below needed no credentials.

## BEFORE — Orbi UPnP port-map table
| idx | WAN port | proto | → internal client | iport | desc |
|---|---|---|---|---|---|
| **0** | **3306** | TCP | **10.0.0.58** (NAS old IP) | 6690 | `upnpclient:6690` |
| 1 | 5510 | TCP | 10.0.0.58 (NAS) | 5510 | `upnpclient:5510` |
| 2 | 41641 | UDP | 10.0.0.79 (Mac) | 41641 | NAT-PMP (Tailscale) |
| 3 | 41643 | UDP | 10.0.0.89 (NAS) | 41643 | NAT-PMP (Tailscale) |

**Root cause:** the "3306 exposure" is a **Synology-created UPnP mapping** — WAN `3306/TCP` forwards to
the NAS's **Synology Drive port 6690** (desc `upnpclient:6690`), targeting the NAS's **old** IP
`10.0.0.58`. It is NOT a MariaDB forward and NOT a hand-made static rule (a static MariaDB rule would be
3306→3306); it was auto-created by a Synology package via UPnP.

## ACTION — deleted the 3306 mapping (unambiguous NAS mapping; explicitly authorized)
`DeletePortMapping(RemoteHost="", ExternalPort=3306, Protocol=TCP)` → **HTTP 200.**

## AFTER — re-enumerated (twice)
| idx | WAN port | proto | → internal | desc |
|---|---|---|---|---|
| 0 | 5510 | TCP | 10.0.0.58 (NAS) | `upnpclient:5510` (**flagged, not deleted**) |
| 1 | 41641 | UDP | 10.0.0.79 (Mac) | Tailscale (benign) |
| 2 | 41643 | UDP | 10.0.0.89 (NAS) | Tailscale (benign) |

**3306 mapping is GONE** — authoritative proof from the router's own table.

## Flagged / left intact (per authorization scope)
- **5510/TCP → NAS (Synology Drive)** — a NAS WAN exposure, but outside the explicit 3306 authorization
  ("ambiguous → ask"). **Recommend removal** (same method) on operator confirmation.
- **41641/41643 UDP (Tailscale NAT-PMP)** — legitimate Tailscale P2P transport; **left intact**
  (removing would degrade Tailscale direct connectivity; UDP, not an admin/DB service).

## Recurrence risk
UPnP is still enabled on the Orbi and a Synology service requested these mappings, so 3306 **could be
re-created**. Durable prevention = disable the NAS-side UPnP/router-port-forwarding (DSM → Control Panel
→ External Access → Router Configuration) or disable UPnP on the Orbi (`08`).

---

## UPDATE — operator disabled UPnP on the Orbi (verified)
After the 3306 deletion, the operator **disabled UPnP** on the router (ADVANCED → Advanced Setup → UPnP
→ off → Apply). Re-running the UPnP-IGD enumeration confirms:
- SSDP discovery no longer lists the router IGD (`http://10.0.0.1:5000/rootDesc.xml` is **gone**; 13
  devices vs 16 before).
- **"NO WANIPConnection/WANPPPConnection control URL found via UPnP."** → the router exposes **no
  port-mapping table at all**.

**Effect:** the 3306 mapping (already deleted), the residual **5510** mapping, and the Tailscale
NAT-PMP mappings are all **cleared**, and **recurrence is prevented** — Synology can no longer auto-open
WAN ports via UPnP. (Tailscale remains functional via DERP/other NAT traversal.)
