# N2C-T · 04 — Router Remediation

Remediation was performed via the **UPnP-IGD protocol** (no login required), not the Orbi web UI — see
`03`. The WAN `3306/TCP` UPnP mapping to the NAS was deleted and verified gone.

## Router UI items still recommended (operator, NETGEAR Orbi at http://10.0.0.1 — needs admin login)
1. **Port Forwarding table:** confirm there is **no static** forward for `3306` (or 5000/5001/10021/22/
   8000/9000/9443/445/2049/5005/5006/8123) to the NAS. The deleted rule was UPnP-dynamic; a static rule
   (if any) is separate and only visible/removable in the UI. (Highly likely none — the exposure was the
   UPnP mapping.)
2. **UPnP:** ADVANCED → Advanced Setup → UPnP. Consider **disabling UPnP** (or leaving it but knowing
   Synology may re-create WAN mappings). If left on, remove the residual **5510** mapping and re-check.
3. **DMZ / Exposed Host:** confirm the NAS is **not** the DMZ host.
4. **DHCP reservation:** reserve the NAS at **10.0.0.89** (the stale mappings pointed at old **10.0.0.58**
   — a reservation prevents IP drift and stale rules).

## Agent-performed vs operator-pending
- **Agent (done, no creds):** enumerated UPnP table; deleted WAN 3306→NAS mapping; re-verified.
- **Operator (pending, needs Orbi login):** confirm no static 3306 forward; disable UPnP / remove 5510;
  confirm no DMZ; set DHCP reservation.

No router credentials or tokens were handled or recorded.
