# N2C-S · 04 — Router / UPnP / Port-Forward Review (OPERATOR)

The agent cannot access the router. **You** perform these at `http://10.0.0.1`; paste the non-secret
results back and they will be recorded here. Router credentials are never entered in chat.

## Most likely cause of the 3306 exposure
A **UPnP-created mapping** (a package/app auto-opened 3306) or a **static port-forward** to the NAS.
MariaDB itself does not open a router port — the router does. Check UPnP **and** the port-forward table.

## Checklist

1. Log into the router/gateway at **http://10.0.0.1** (Comcast/Xfinity gateway, based on the WAN
   hostname).
2. Find **Port Forwarding** (Advanced → Port Forwarding / Gateway → Firewall / NAT).
3. **Remove any forward to the NAS** (LAN IP **10.0.0.89** — note: previously 10.0.0.58; check both,
   or match by device name/MAC) for these ports:
   `3306` (critical), `5000`, `5001`, `10021`, `22`, `8000`, `9000`, `9443`, `445`, `2049`, `5005`,
   `5006`, `8123`. Leave `443` only if you knowingly run a hardened public reverse proxy (document it).
4. Find **UPnP** settings.
5. Note whether UPnP is **enabled** and list any **active UPnP mappings** to 10.0.0.89 (especially 3306).
6. **Remove** any UPnP mapping to the NAS; **disable UPnP** if you don't rely on it (recommended — it's a
   common cause of silent exposure).
7. Check for a **DMZ host** setting — ensure the NAS is **not** the DMZ host (a DMZ exposes ALL ports).
8. Save/Apply. Reboot the router only if the UI requires it.

## Please report (paste back)
- Was there a **port-forward for 3306** to the NAS? (yes/no)
- Any other forwards to the NAS (10.0.0.89 / .58)? List ports.
- Is **UPnP enabled**? Any **UPnP mappings** to the NAS? (esp. 3306)
- Is the NAS set as **DMZ host**? (yes/no)
- Were **5000 / 5001 / 443** forwarded?
- What did you **remove**?
- Is **443** intentionally exposed for anything? If so, what?

_(Operator results will be recorded below.)_

### Operator results — _pending_
