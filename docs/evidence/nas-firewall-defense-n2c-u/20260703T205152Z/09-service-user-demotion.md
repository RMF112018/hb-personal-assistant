# N2C-U · 09 — Service-User Demotion (runtime-user / admin split) — PASS

Operator-performed and operator-attested (svc SSH is now denied, so agent re-verification would require
bfetting; the operator provided the proof below). 2026-07-04.

## Proof (operator-run, non-secret)
- **Direct SSH as `personal-assistant-svc` → Permission denied** — expected/acceptable after demotion
  (runtime user no longer needs shell; least privilege).
- **`bfetting` SSH + sudo → PASS** (control/deploy path intact; still `administrators` + `sudo-ok`).
- **`sudo -u personal-assistant-svc id`:** `uid=1028(personal-assistant-svc) gid=100(users)
  groups=100(users),1023(http)` → **`administrators` removed**.
- **Runtime read/write/traverse/write-proof PASS** for (as svc):
  `…/app-support/{auth,security,db,db/backups,logs,evidence,cache,tmp}` and `…/runtime`.

## Assessment vs target model
| Target | Result |
|---|---|
| `bfetting` = SSH/control/deploy/admin | ✅ verified |
| `personal-assistant-svc` = non-admin runtime owner | ✅ (uid 1028, `users`+`http`, no `administrators`) |
| svc retains runtime write access | ✅ write-proof across all runtime folders |
| svc no longer needs Docker/admin | ✅ (not in administrators; docker.sock root-only) |

## Operational change (carry into N3+)
Direct `ssh personal-assistant-svc@…` **no longer works.** Future NAS operations use **`bfetting`** for
SSH/sudo, and **`sudo -u personal-assistant-svc <cmd>`** to act as the runtime user. Any N3 tooling that
previously connected as svc must be updated accordingly.

## Verdict
**Service-user demotion gate: PASS.** Runtime-user/admin split complete; control path preserved via bfetting.
