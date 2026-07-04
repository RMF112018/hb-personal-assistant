# N2C-S · 05 — DSM Firewall Review (OPERATOR + optional read-only sudo)

## Agent read-only attempt
`/usr/syno/bin/synofirewall --status` as `personal-assistant-svc` → **requires root** (Permission
denied); `sudo -n …` → **"a password is required"** (svc is not NOPASSWD). The agent will **not** handle
a password. So DSM firewall state is **operator-obtained**.

## Optional: you run the read-only status yourself (svc is in `administrators`, so password sudo works)
```
ssh -tt -p 10021 personal-assistant-svc@100.66.28.14 'sudo /usr/syno/bin/synofirewall --status'
```
Paste the non-secret output. (Do not use the `!` prefix unless you've confirmed your harness supports it;
in normal zsh it will not work.)

## DSM firewall checklist (defense-in-depth behind the router fix)
1. DSM → **Control Panel → Security → Firewall** → **Enable firewall**.
2. Create rules on the **LAN/all** interface:
   - **Allow** SSH `10021` from **LAN subnet (10.0.0.0/24)** and **Tailnet (100.64.0.0/10)** only.
   - **Allow** DSM `5000/5001` from LAN/Tailnet only.
   - **Allow** future HB `8000` from LAN/Tailnet only (or keep loopback-only during smoke).
   - **Deny** `3306` (MariaDB) from any non-LAN source (ideally allow only `127.0.0.1`/LAN if used at all).
   - **Deny all** other unsolicited inbound (final default-deny rule).
3. Confirm any **Docker-published** ports are intentional (none HB-related should be public).
4. Apply.

> The router fix (`04`) is the primary control (it stops WAN traffic before the NAS). The DSM firewall is
> a second layer in case a forward is ever re-created (e.g., UPnP).

## Please report
- Was the DSM firewall **enabled** before? Is it enabled now?
- Does any rule allow `3306` / DSM / SSH from **non-LAN/Tailnet** sources?
- What rules did you change?

### Operator results — _pending_
