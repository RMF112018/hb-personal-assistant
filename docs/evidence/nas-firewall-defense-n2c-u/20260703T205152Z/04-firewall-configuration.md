# N2C-U · 04 — Firewall Configuration (operator-applied)

Applied by the **operator** via DSM (Control Panel → Security → Firewall) through the lockout-safe SSH
tunnel (`https://127.0.0.1:15001` = NAS localhost). Agent did not click the UI (no browser). No sudo.

## Rules applied (per plan `03`, operator-attested)
| # | Action | Source | Ports | Proto |
|---|---|---|---|---|
| 1 | Allow | 10.0.0.0/24 (LAN) | All | All |
| 2 | Allow | 100.64.0.0/10 (Tailscale) | All | All |
| 3 | Deny | All | All | All |

Firewall enabled with allow-before-deny ordering. The Tailscale allow (100.64.0.0/10) was explicitly
included at the operator's direction to preserve tailnet control access.

## Machine-confirmable vs attested
- **Machine-proven (this phase):** access from LAN + Tailnet is preserved after apply (`05`).
- **Operator-attested (not machine-proven):** the firewall is *enabled* and the *deny* rule is effective.
  Reason: the agent's only vantages (LAN 10.0.0.79, tailnet 100.85.102.83) are both **allowed**, so they
  cannot observe the deny; and `synofirewall --status` requires sudo. To machine-confirm enabled state,
  operator may run (interactively; agent will not handle the password):
  `ssh -tt -p 10021 personal-assistant-svc@100.66.28.14 'sudo /usr/syno/bin/synofirewall --status'`

---

## UPDATE — machine proof (operator-run sudo, non-secret output pasted)
- `synofirewall --info` → **`fw_enabled = 1`** (firewall ENABLED).
- `synofirewall --enum IPV4`:
  - LAN allow: `-s 10.0.0.0/255.255.255.0 -j RETURN`
  - Tailnet allow: `-s 100.64.0.0/255.192.0.0 -j RETURN`
  - deny-all: `-A FORWARD_FIREWALL -j DROP` and `-A INPUT_FIREWALL -j DROP`
- `synofirewall --export`: profile `default` status `true`; rule 0 allow 10.0.0.0/255.255.255.0;
  rule 1 allow 100.64.0.0/255.192.0.0; rule 2 deny all.

→ Firewall **enabled** with allow-before-deny confirmed at the rule engine (both INPUT and FORWARD
chains default-DROP; LAN + Tailnet RETURN above). Enabled-state is now **machine-proven**, not merely
attested. No passwords/credentials in the pasted output.
