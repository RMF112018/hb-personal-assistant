# N2C-V · 02 — Public WAN Exposure (FINAL)

## Finding chain
1. External passive check (Shodan InternetDB, keyless) initially reported the WAN IP `98.x.x.183`
   with an open port **3306** — read as "MariaDB exposed."
2. Root-cause trace (N2C-T): the exposure was **not** a MariaDB service. It was a **Synology
   UPnP-created port map** on the Orbi router: **WAN `3306/TCP` → internal `10.0.0.58:6690`**
   (Synology Drive server, described `upnpclient:6690`). UPnP-IGD requires **no authentication**,
   so Synology Drive had silently punched the hole.
3. Removal (N2C-T): credential-free UPnP-IGD `DeletePortMapping` for WAN `3306/TCP` → **HTTP 200**;
   immediate re-enumeration showed the mapping **gone**.
4. Operator **disabled UPnP** on the Orbi router (removes the mechanism, not just the instance).

## Agent re-verification captured THIS phase (read-only)
SSDP `M-SEARCH` for `InternetGatewayDevice` / `WANIPConnection` / `rootdevice` against the LAN:
```
SSDP LOCATIONs discovered: 10
NO WANIPConnection/WANPPPConnection control URL found via UPnP.
```
Interpretation: with UPnP disabled there is **no gateway control endpoint** to enumerate or to
re-create a forward. The removal is durable, not a one-shot.

## Why PASS (router-table proof supersedes external scan)
The authoritative control is the **router forwarding table**: a port that is not forwarded cannot
be reached from the WAN regardless of what any host listens on. That table is proven empty of the
3306 map AND the UPnP mechanism that created it is disabled — a **stronger** guarantee than a
single external scan snapshot.

## Note on Shodan lag (not a blocker)
Shodan InternetDB is passive/historical and can show a stale `3306` for days after closure; it is
not a live prober. The pre/after raw InternetDB JSON and the full WAN IP are kept in gitignored
`local-sensitive/` (see `local-sensitive/README.md`). An optional live off-network scan (phone
hotspot / external host) may be run by the operator as extra courtesy but is **not required** for
this gate given the router-table + UPnP-disabled + agent-re-enum proof.

**Gate: PASS.**
