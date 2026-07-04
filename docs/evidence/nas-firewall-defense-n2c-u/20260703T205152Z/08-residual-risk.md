# N2C-U · 08 — Residual Risk & Open Items

- **WAN exposure: CLOSED** (N2C-T) — UPnP mapping deleted + UPnP disabled; no router forwarding path.
- **DSM firewall: ENABLED (machine-proven)** — `fw_enabled=1`; LAN + Tailnet RETURN above default DROP
  (INPUT + FORWARD). Gate PASS.
- **MariaDB still binds `0.0.0.0:3306` locally** — now protected by (a) no WAN forward, (b) DSM firewall
  source restriction. Optional later: bind MariaDB to localhost/LAN (package/my.cnf) — deferred.
- **6690 (Synology Drive) / 5006 (WebDAV) / 8123 (Home Assistant) / 2049 (NFS) / 445-139 (SMB)** — still
  bind broadly but are LAN/Tailnet-only now (firewall) and not WAN-forwarded.
- **UPnP recurrence:** prevented (disabled; IGD absent, re-verified).
- **443:** not WAN-forwarded; LAN/Tailnet only under firewall.
- **bfetting control path: VERIFIED** — SSH as bfetting + `administrators` + `sudo-ok`. Alternate
  control/deploy path proven; svc demotion now safe when chosen.
- **personal-assistant-svc DEMOTED** — removed from `administrators` (now `users`+`http`); retains
  runtime write access (write-proof PASS across all app-support folders + runtime). Direct svc SSH now
  denied → future NAS ops via **bfetting** + `sudo -u personal-assistant-svc`. Gate PASS (`09`).
- **N3:** remains **prohibited** — exposure + firewall + bfetting + **svc-demotion** gates now PASS; N3
  now needs **only explicit operator N3 authorization** (DB-copy/smoke/cutover out of scope).
