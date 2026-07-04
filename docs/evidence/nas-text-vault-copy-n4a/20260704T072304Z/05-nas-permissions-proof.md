# 05 — NAS Permissions Proof (least-privilege)

## Target metadata after copy (no key contents)
| Path | Mode | Owner |
|---|---|---|
| `<app-support>/security` | 700 (`drwx------`) | `personal-assistant-svc:users` |
| `<app-support>/security/text-vault` | 700 (`drwx------`) | `personal-assistant-svc:users` |
| `<app-support>/security/text-vault.key` | 600 (`-rw-------`) | `personal-assistant-svc:users` (size 44) |
| `<app-support>/security/text-vault/*.enc` | 600 each | `personal-assistant-svc:users` |
| blob count | 7,202 | — |

## Service-user access proof
The coherence proof itself was executed **as `personal-assistant-svc`** (`sudo -u personal-assistant-svc python3`),
which required and demonstrated: svc can traverse `security/` + `security/text-vault/`, stat/list the blobs, read
the key path, and open the DB `mode=ro`. Success of that run (below / see 06) is the access proof.

## Lockdown confirmation (agent, read-only as bfetting)
`ls` of `<app-support>/security/` as bfetting → **Permission denied** (700 svc). Correct: the control/admin user
cannot read the runtime user's secret material without sudo; least-privilege intact.

No key contents were read or printed (`sudo cat` on the key was never used).
