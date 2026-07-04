# N2C-U · 06 — Post-Firewall Exposure Check

Masked WAN `98.x.x.183` (full only in `local-sensitive/`).

| Signal | Result |
|---|---|
| Router UPnP-IGD | still **absent** ("NO WANIPConnection control URL") — UPnP stays disabled; recurrence prevented |
| Shodan InternetDB | still `ports:[3306]` — **passive/stale**; lags until Shodan re-scans (days) |
| WAN 3306 forward | removed in N2C-T (UPnP mapping deleted + UPnP disabled) — root cause gone |

## Live off-network confirmation
Still recommended as the authoritative check (Shodan is passive): from a device off the home network,
scan the WAN IP for `3306, 5510, 6690, 5000, 5001, 443, 10021, 8000, 9000, 9443, 445, 139, 111, 2049,
5005, 5006, 8123` → expected all closed. The router-side proof (UPnP mapping deleted + UPnP disabled +
no IGD) already establishes there is no forwarding path; the DSM firewall is an added second layer.

Operator-provided off-network results (if any): _pending_.
