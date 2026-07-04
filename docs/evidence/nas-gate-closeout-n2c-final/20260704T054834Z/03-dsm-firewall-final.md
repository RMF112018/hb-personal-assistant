# N2C-V · 03 — DSM Firewall Defense-in-Depth (FINAL)

## Design
The router UPnP removal (`02`) is the **primary** control (stops WAN traffic before the NAS). The
DSM firewall is a **second layer** so that even if a forward is ever re-created, only LAN and the
Tailnet can reach the NAS's management/service ports. Rule order is **allow-before-deny** with a
final **default-deny**.

## Applied state (operator machine proof — `synofirewall --info/--enum/--export`)
- `fw_enabled = 1` (firewall enabled; it was **not** enabled before this phase).
- **Allow** SSH `10021` / DSM `5000-5001` / (future) HB `8000` from **LAN `10.0.0.0/24`** → `RETURN`.
- **Allow** the same from **Tailnet `100.64.0.0/10`** → `RETURN` (mandatory: the agent's SSH is
  tailnet-sourced; without this the change would have locked out remote management).
- **Deny all** other unsolicited inbound → default `DROP` (`INPUT_FIREWALL` / `FORWARD_FIREWALL`).

## Lockout-safety
Applied by the operator through a **lockout-proof path**: an SSH **local port-forward to the DSM
loopback** (`-L`), so DSM evaluates the change as originating from `127.0.0.1` and the operator
could revert if the deny-all had been mis-ordered. Post-apply, **SSH over the Tailnet survived**
(management access retained), confirming the allow rules precede the deny.

## Residual note
- `8000` is allowed from LAN/Tailnet only; there is no public map for it. During any future
  copied-DB smoke (N3+) the backend should still bind loopback/LAN, not `0.0.0.0` publicly.
- No agent-side `synofirewall` re-run this phase: it requires root, `svc` is no longer NOPASSWD
  and is now demoted, and the agent does not handle passwords. State is taken from the operator's
  machine export, which is a verbatim CLI dump (not a screenshot/attestation).

**Gate: PASS.**
