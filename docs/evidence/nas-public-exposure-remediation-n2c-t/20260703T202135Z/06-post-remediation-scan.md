# N2C-T · 06 — Post-Remediation Verification

Masked WAN `98.x.x.183`. Raw JSON in `local-sensitive/internetdb-{before,after}.json`.

| Signal | Before | After | Notes |
|---|---|---|---|
| **Router UPnP table (authoritative)** | WAN 3306→NAS present | **3306 REMOVED** (verified ×2) | direct read of the router's forwarding table — strongest proof |
| Shodan InternetDB (passive) | ports:[3306] | ports:[3306] | **stale** — passive DB lags; not an active probe |
| Mac→WAN hairpin (non-authoritative) | (mixed earlier) | 3306 **not connectable** | corroborates closed; hairpin unreliable, informational only |
| NAS listeners | 3306 on 0.0.0.0 | unchanged | local bind ≠ WAN exposure; router is decisive |
| Tailscale Serve/Funnel | off | off | unchanged |

## Interpretation
The **router no longer forwards WAN 3306 to the NAS** (proven by direct UPnP-table read). Shodan still
lists 3306 because its data is passive/historical and will clear only when Shodan re-scans (days). The
authoritative live confirmation is an **operator off-network scan** (phone on cellular / external port
checker) of the WAN IP for 3306 → expected **closed**.

## Requested operator live check (off-network) for: 3306, 10021, 8000, 5000, 5001, 9000, 9443, 445, 2049, 5005, 5006, 8123
Expected: all closed from WAN.
