# N2C-U — Closeout · DSM Firewall Defense-in-Depth

UTC 20260703T205152Z · Branch `audit/nas-public-exposure-remediation-n2c-s-20260703T200551Z` @ `4fe34348`
Evidence: `docs/evidence/nas-firewall-defense-n2c-u/20260703T205152Z/` (00–08 + local-sensitive).

## Result: **PASS** — DSM firewall enabled (machine-proven), allow-before-deny, trusted access preserved.

## What happened
- **DSM SSH tunnel** established (`-L 15001:127.0.0.1:5001`) — lockout-safe (DSM sees localhost). Browser
  automation unavailable, so the **operator applied** the firewall via the tunnel; agent supplied rules
  + verified access. **Tunnel closed at end (no stale process).**
- **Rules applied** (operator-attested): Allow LAN `10.0.0.0/24` → Allow Tailnet `100.64.0.0/10` →
  Deny all. Allow-before-deny; Tailscale allow explicitly included.
- **Access validation (machine-proven):** SSH over **tailnet** ✅ and **LAN** ✅ both work; DSM tunnel
  200 ✅; Tailscale Serve/Funnel OFF ✅; port 8000 not listening ✅. **No lockout.**
- **Enabled-state / deny: MACHINE-PROVEN** (operator-run sudo) — `synofirewall --info` `fw_enabled=1`;
  `--enum`/`--export` show rule 0 allow LAN 10.0.0.0/24, rule 1 allow Tailnet 100.64.0.0/10, rule 2
  deny-all (default DROP on INPUT_FIREWALL + FORWARD_FIREWALL).
- **bfetting control path VERIFIED** (operator-run): SSH as bfetting + `administrators` + `sudo-ok` —
  clears an N3 precondition; svc demotion now safe when chosen.
- **service-user demotion COMPLETE** (operator-run, `09`): `personal-assistant-svc` removed from
  `administrators` (now uid 1028, `users`+`http`); runtime write-proof PASS across all app-support
  folders + runtime; direct svc SSH now denied → future NAS ops via **bfetting** + `sudo -u personal-assistant-svc`.
- **Exposure:** WAN 3306 already closed in N2C-T (UPnP mapping deleted + UPnP disabled; re-verified IGD
  absent). Shodan still lists 3306 — passive/stale.

## Boundaries maintained
No DB copy/open/migrate; no secrets/MSAL/Procore/Fernet/Text-Vault; no vault; no HB backend/container;
no Portainer restart; no schedulers/watchers; **no router change this phase**; **no sudo executed**;
no credentials/cookies/tokens/screenshots handled. WAN IP masked in committed evidence. Tunnel closed.
**Nothing committed, nothing pushed.**

## N3
Exposure **PASS** (N2C-T); firewall defense-in-depth **PASS**; **bfetting control path PASS**;
**service-user demotion PASS** (`09`). N3 still **prohibited** — remaining: **explicit operator N3
authorization only**. DB-copy/smoke/cutover remain out of scope. Operational: svc no longer SSH-able;
use bfetting + `sudo -u personal-assistant-svc`.
