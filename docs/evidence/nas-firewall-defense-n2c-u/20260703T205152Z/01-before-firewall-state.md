# N2C-U · 01 — Before Firewall State

UTC 20260703T205152Z · Branch `audit/nas-public-exposure-remediation-n2c-s-20260703T200551Z` @ `4fe34348`.

## Prior result (N2C-T): exposure gate PASS
WAN 3306 UPnP mapping deleted; **UPnP disabled on the Orbi** (router IGD gone, no port-map table);
recurrence prevented. This phase adds the DSM firewall as a second layer.

## Critical safety fact — my SSH is Tailnet-sourced
`SSH_CONNECTION` shows source **100.85.102.83** (Mac tailnet IP) → 100.66.28.14 (NAS tailnet). So the
agent's control channel arrives over **Tailscale**. A **Tailnet allow rule (100.64.0.0/10) is mandatory
before any deny**, or the agent (and possibly the operator, if managing DSM over tailnet) is locked out.
The Mac is also on-LAN (10.0.0.79), so SSH via the NAS LAN IP 10.0.0.89 is a fallback covered by the LAN
allow rule.

## NAS listeners (0.0.0.0 unless noted)
Listening: 10021 (SSH), 443, 5000, 5001 (DSM), **3306 (MariaDB)**, **6690 (Synology Drive)**, 2049 (NFS),
445/139 (SMB), 111 (RPC), 8123 (Home Assistant); 5006 IPv6 (WebDAV).
Not listening: 22, 8000 (HB), 9000/9443 (Portainer), 5510, 5005.
Tailscale Serve/Funnel: **OFF**.

These bind broadly on the NAS; after N2C-T they are no longer WAN-forwarded. The DSM firewall will
constrain them to LAN/Tailnet sources as defense-in-depth.
