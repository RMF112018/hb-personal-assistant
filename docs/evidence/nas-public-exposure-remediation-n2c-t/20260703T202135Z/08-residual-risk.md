# N2C-T · 08 — Residual Risk & Open Items

- **WAN 3306 exposure: CLOSED** ✅ — UPnP mapping deleted, and **UPnP now disabled** on the Orbi
  (router IGD gone, no port-map table). Recurrence prevented.
- **Residual 5510 NAS mapping:** cleared by the UPnP disable ✅.
- **MariaDB still binds `0.0.0.0:3306` locally** — no longer WAN-forwarded. Optional later hardening:
  bind MariaDB to localhost/LAN — deferred, not needed for exposure closure.
- **Tailscale NAT-PMP mappings** removed by UPnP disable — Tailscale stays functional (DERP/other NAT
  traversal); direct-connection optimization may occasionally relay. Accepted trade-off.
- **Static port-forward table (Orbi UI):** not machine-verified (needs router login). Exposure was
  UPnP-based; recommend a 10-sec glance at ADVANCED → Advanced Setup → Port Forwarding to confirm no NAS
  rule. **Optional/courtesy.**
- **Live off-network scan:** recommended courtesy confirmation (Shodan is passive and still lists 3306
  until it re-scans).
- **DSM firewall not enabled** — optional defense-in-depth (`05`).
- **bfetting control path:** still unverified (no SSH key) — unchanged.
- **personal-assistant-svc still in `administrators`** — demotion deferred (safe; svc owns auth/security).
- **N3:** remains **prohibited** pending control-path verification + explicit N3 authorization
  (exposure gate itself is now PASS).
