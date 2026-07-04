# N2C-V · 01 — Consolidated Gate Matrix (FINAL)

Legend: **PASS** = supported by machine and/or operator proof · **NOT RUN** = deliberately not
executed (out of N2 scope / prohibited until authorized).

| # | Gate | Result | Evidence / basis |
|---|------|--------|------------------|
| 1 | Schema-version drift (`LATEST_SCHEMA_VERSION` 97→98) | **PASS** | N2 `b912b4ed`; scratch-DB `apply()==98`; regression guard `tests/test_schema_version_head_consistency.py`; both bundles green |
| 2 | Scaffold `.dockerignore` test drift | **PASS** | N2B `4fe34348`; excludes secrets/config/db, NOT `src/hb_assistant/{auth,security}` |
| 3 | Auth/security ACL hardening (0777 → tightened) | **PASS** | Operator proof (N2C-R/S): permissive world-write removed on auth/security dirs |
| 4 | Public WAN exposure (mistaken "MariaDB 3306") | **PASS** | Root cause = Synology UPnP map WAN 3306→`10.0.0.58:6690`; deleted via UPnP-IGD (HTTP 200) + re-enum absent (N2C-T); operator disabled UPnP; **agent re-enum this phase: no WAN control URL** |
| 5 | UPnP recurrence prevention | **PASS** | UPnP disabled on Orbi; agent SSDP M-SEARCH finds **no** WANIPConnection service → nothing can re-create a forward |
| 6 | DSM firewall defense-in-depth | **PASS** | `synofirewall --info/--enum/--export`: `fw_enabled=1`; allow LAN `10.0.0.0/24` RETURN + allow Tailnet `100.64.0.0/10` RETURN + **default DROP**; SSH-over-tailnet survived apply |
| 7 | bfetting admin control path | **PASS** | `uid=1026(bfetting) gid=100(users) groups=100(users),101(administrators)`; SSH + sudo verified BEFORE svc demotion |
| 8 | Service-user least-privilege (svc demotion) | **PASS** | `uid=1028(personal-assistant-svc) gid=100(users) groups=100(users),1023(http)` — removed from `administrators`; runtime write-proof PASS on 9 folders; **agent-verified svc SSH now Permission denied** |
| 9 | Port 8000 (future HB backend) posture | **PASS-with-note** | No public/UPnP map for 8000; DSM firewall default-deny covers non-LAN/Tailnet; backend not yet running (N3+). Note: bind must stay loopback/LAN during copied-DB smoke |
| 10 | Runtime write access after demotion | **PASS** | svc (via `sudo -u personal-assistant-svc`) writable on auth/security/db/backups/logs/evidence/cache/tmp/runtime |

## Deliberately NOT RUN (prohibited until explicit authorization)
| Item | State |
|------|-------|
| Copy live Mac DB → NAS | **NOT RUN — prohibited (N3)** |
| Open/migrate any production/copied DB | **NOT RUN — prohibited (N3)** |
| Copied-DB `/health` smoke | **NOT RUN — prohibited (N3)** |
| Start HB backend / container / Portainer | **NOT RUN — prohibited** |
| Copy secrets / MSAL cache / Procore creds / Fernet / Text-Vault keys | **NOT RUN — prohibited** |
| Mount live Obsidian vault / source roots | **NOT RUN — prohibited** |
| N3 authorization | **NOT GRANTED** |

## Overall
All in-scope N2 security/technical gates are **PASS**. No blocker remains except the **explicit
operator authorization** required to begin N3.
