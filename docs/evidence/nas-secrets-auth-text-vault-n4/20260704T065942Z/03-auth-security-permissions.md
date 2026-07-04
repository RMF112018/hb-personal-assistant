# 03 — Auth / Security Permissions (least-privilege check)

## NAS app-support subdir metadata (read-only stat; no content listed)
| Path | Mode | Owner | Notes |
|---|---|---|---|
| `<app-support>/auth` | `drwx------` (700) | `personal-assistant-svc:users` | not listable without sudo (correct) |
| `<app-support>/security` | `drwx------` (700) | `personal-assistant-svc:users` | not listable without sudo (correct) |
| `<app-support>/security/text-vault` | — | — | **ABSENT** (no vault material on NAS yet) |
| `<app-support>/db` | `drwxrwxrwx` (777) | `bfetting:users` | contains the copied DB (file itself `svc:users` 600) |
| `<app-support>/logs`,`tmp`,`cache`,`evidence` | `drwxrwxrwx` (777) | `bfetting:users` | runtime working dirs |
| `<service-root>/runtime` | `drwxrwxrwx` (777) | `bfetting:users` | runtime dir |

## Assessment
- **auth + security are least-privilege** (`700`, owned by the demoted runtime user) — bfetting (even in
  administrators) cannot read them without sudo; this session did not attempt to (no sudo, no content dump).
- The 777 working dirs (db/logs/tmp/cache/evidence/runtime) are broad but hold no secrets; the sensitive DB file
  inside `db/` is itself `600 svc:users`. Tightening these dirs to `750`/`700 svc` is a **later-phase hardening
  option** (not required for N4; would need sudo).
- Target permissions for the deferred Text Vault copy (when authorized): dir `security/text-vault` = `0700`,
  each `.enc` = `0600`, key `0600`, all `chown personal-assistant-svc:users` — matching the existing `700 svc`
  posture of `security/`.

## Boundary held
No `auth`/`security` contents were listed or read; only directory-node metadata (mode/owner) was captured.
