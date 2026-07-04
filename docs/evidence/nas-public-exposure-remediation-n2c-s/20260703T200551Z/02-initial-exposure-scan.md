# N2C-S · 02 — Initial External Exposure Scan (BEFORE)

Source: **Shodan InternetDB** (`https://internetdb.shodan.io/<WAN_IP>`) — keyless external vantage,
**passive/historical** (reflects Shodan's last internet-wide scan of the IP, not a live probe).
Timestamp: 20260703T200551Z. Full WAN IP stored only in `local-sensitive/wan-ip.txt` (gitignored).

## Result (masked)

WAN IP: **98.x.x.183** (Comcast residential, FL). Raw: `local-sensitive/internetdb-before.json`.

```
{"ip":"98.x.x.183","ports":[3306],"hostnames":["…comcast.net"],"tags":[],"vulns":[],"cpes":[]}
```

| Port | Service | Reported exposed (before) |
|---|---|---|
| **3306** | **MariaDB/MySQL** | **YES ⚠️** |
| 5000 | DSM HTTP | no (Shodan) |
| 5001 | DSM HTTPS | no (Shodan) |
| 443 | HTTPS | no (Shodan) |
| 10021 | SSH | no (Shodan) |
| 8000 | HB (future) | no (Shodan) |

## Notes
- **3306 present** → MariaDB is publicly exposed and must be closed (`04`/`05`/`06`).
- Shodan is passive: absence of a port here is **not** proof-closed (Shodan may not have probed it), and
  after remediation Shodan may **still list 3306 until it re-scans** (can lag days/weeks) — so the
  authoritative post-fix confirmation is a **live off-network scan**, with Shodan as slower corroboration
  (`07`).
- N2C-R also observed (via unreliable same-LAN hairpin) DSM 5000/443 responding — to be resolved by the
  router/firewall review regardless.

## Verdict
**BEFORE = FAIL** (MariaDB 3306 publicly exposed).
