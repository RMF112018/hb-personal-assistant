# N2C-T · 01 — Before State

UTC 20260703T202135Z. Full WAN IP only in `local-sensitive/wan-ip.txt`; masked here as `98.x.x.183`.

## External (Shodan InternetDB, passive)
`{"ip":"98.x.x.183","ports":[3306],...}` → **3306 reported OPEN** (unchanged from N2C-S). Shodan is
passive/historical — reflects a past scan; it lags real changes by days.

## NAS local listeners (read-only)
- **3306/MariaDB** listening `0.0.0.0`. SSH 10021, DSM 5000/5001/443, NFS 2049, SMB 445, WebDAV 5006,
  HA 8123 bind all-interfaces. **8000 and Portainer 9000/9443 NOT listening.**
- Tailscale Serve/Funnel **OFF**. No `upnpc` tool on Mac or NAS.

## Conclusion
3306 is exposed at the WAN. Cause to be identified (`03`). Local listening ≠ WAN exposure; the router
forwarding table is decisive.
