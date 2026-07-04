# N2C-U · 05 — Access Validation (post-firewall)

All checks after the firewall was applied — **access from trusted sources preserved:**

| Check | Result |
|---|---|
| SSH over **Tailnet** (100.66.28.14), src 100.85.102.83 | ✅ works — `personal-assistant-svc@TheLakeHouseNAS` |
| SSH over **LAN** (10.0.0.89), src 10.0.0.79 | ✅ works — `OK-LAN` (host key accepted) |
| DSM via tunnel (`https://127.0.0.1:15001`) | ✅ HTTP 200 |
| Tailscale Serve / Funnel | ✅ OFF |
| Port 8000 (HB) | ✅ not listening |
| 3306 local bind | still `0.0.0.0:3306` (bind unchanged; now source-filtered by firewall + no WAN forward) |
| `synofirewall --status` (non-sudo) | needs sudo — operator-run only |

**Interpretation:** the LAN and Tailscale allow rules work (both SSH paths + DSM survive). No lockout.
Note: preserved trusted-source access does **not** by itself prove the firewall is *enabled* (same
outcome if it were off) — enabled-state is operator-attested (`04`).

---

## UPDATE — machine proofs (operator-run)
- **DSM firewall enabled + rules:** `synofirewall --info` `fw_enabled=1`; `--enum`/`--export` show
  LAN 10.0.0.0/24 RETURN, Tailnet 100.64.0.0/10 RETURN, default DROP (INPUT+FORWARD). See `04`.
- **bfetting control path VERIFIED:** SSH as `bfetting` succeeds; `groups` include **administrators**;
  `sudo` works (`sudo-ok`). → the alternate SSH/control/deploy path is now proven (was BLOCKED in
  N2C-R). This also means `personal-assistant-svc` can be safely demoted later (svc already owns
  auth/security). No passwords handled/recorded.
- **svc access intact:** SSH as `personal-assistant-svc` over Tailnet still works post-firewall.
