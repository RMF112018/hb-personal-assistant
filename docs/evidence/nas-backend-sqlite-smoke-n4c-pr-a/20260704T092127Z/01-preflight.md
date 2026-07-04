# 01 — Preflight

| Item | Value |
|---|---|
| NAS host | `TheLakeHouseNAS` |
| SSH alias | `hb-nas` (Tailscale) |
| Runtime user (container) | `personal-assistant-svc` (uid 1028) |
| Production DB | `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite` |
| DB visible to `bfetting` | **No** (mode 600, owner svc) |
| Docker for `bfetting` | **Requires interactive sudo** (`sudo -n` fails) |

## Inherited gates

| Phase | Verdict |
|---|---|
| N3 copied DB | PASS |
| N4B benchmark | PASS |
| N4C backend smoke | PASS |
| PR A hardening @ `9bcf7e2e` | Code committed locally |

## Phase boundary

Bounded re-smoke only — not PR C, not persistent service install, not cutover.
