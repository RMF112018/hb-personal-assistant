# N2C-T · 05 — DSM Firewall (defense-in-depth) — OPERATOR PENDING

DSM is reachable (tunnel `https://127.0.0.1:15001` and directly on-LAN), but firewall configuration
requires **DSM admin login** (credentials the agent does not handle) and `sudo` for CLI status
(`sudo -n synofirewall` → "password required"; svc not NOPASSWD). Not changed this phase.

## Recommended DSM firewall rules (Control Panel → Security → Firewall)
Apply **allow-before-deny** so LAN/Tailnet access is never lost:
1. **Allow** from **10.0.0.0/24** (LAN) and **100.64.0.0/10** (Tailnet): SSH 10021, DSM 5000/5001, future HB 8000.
2. **Deny** 3306 / DSM / SSH / 8000 from all other (WAN) sources.
3. **Default-deny** remaining unsolicited inbound (only after the allow rules exist).

This is a second layer behind the router fix (`03`/`04`); the router already stops WAN 3306.

## Optional operator-run read-only status
`ssh -tt -p 10021 personal-assistant-svc@100.66.28.14 'sudo /usr/syno/bin/synofirewall --status'`
(svc is in administrators → password sudo works; agent will not handle the password).
