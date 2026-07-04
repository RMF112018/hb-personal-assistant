# N2C-U · 07 — N3 Firewall Gate

## Verdict: **PASS** — DSM firewall enabled and machine-proven; trusted access preserved.

| Criterion | State |
|---|---|
| DSM firewall enabled | ✅ **machine-proven** — `synofirewall --info` `fw_enabled=1` |
| LAN 10.0.0.0/24 allowed | ✅ `-s 10.0.0.0/255.255.255.0 -j RETURN` (rule 0) + LAN SSH works |
| Tailnet 100.64.0.0/10 allowed | ✅ `-s 100.64.0.0/255.192.0.0 -j RETURN` (rule 1) + tailnet SSH works |
| All other inbound denied | ✅ default `DROP` on INPUT_FIREWALL and FORWARD_FIREWALL (rule 2 deny all) |
| SSH over Tailnet works | ✅ |
| DSM access works | ✅ (tunnel 200) |
| Tailscale Serve/Funnel off | ✅ |
| Port 8000 not listening | ✅ |
| WAN 3306 closed | ✅ (N2C-T: UPnP mapping deleted + UPnP disabled; Shodan stale-only) |

## Basis for PASS
All firewall criteria are now **machine-proven** (operator-run `synofirewall --info/--enum/--export`):
enabled, allow-before-deny ordering, LAN + Tailnet RETURN above a default DROP on both INPUT and FORWARD
chains. Trusted-source access (LAN + tailnet + DSM) verified intact — no lockout.

## Relationship to N3
- **Public-exposure gate: PASS** (N2C-T — root cause removed).
- **Firewall defense-in-depth gate: PASS** (this phase).
- Remaining N3 blockers are non-exposure: **bfetting control path — now VERIFIED** (`05`), leaving the
  **svc-demotion decision** and **explicit operator N3 authorization**. DB-copy/smoke/cutover remain out
  of scope.
