# 06 — NAS Copy Validation

## bfetting-perspective validation (completed, no sudo)

Ran as bfetting against the placed final file via NAS `python3` + `sqlite3` (`mode=ro`):

| Check | Result |
|---|---|
| `PRAGMA quick_check` | `ok` |
| `PRAGMA integrity_check` (full) | `ok` |
| `PRAGMA page_count` | 1,013,582 (× 4,096 = 4,151,631,872 B) |
| table count (`sqlite_schema`) | 506 (matches source + local copy) |
| `MAX(schema_migrations.version)` | 98 |

## Hash equivalence (Step 7) — PASS

| Artifact | SHA-256 |
|---|---|
| local backup copy | `4b2d8aab…eccc3` |
| NAS placed file (final) | `4b2d8aab…eccc3` |

**Match** — the NAS copy is byte-identical to the validated local copy. (Full hashes in `local-sensitive/`.)

## service-user (`personal-assistant-svc`) validation — PASS (operator sudo proof)

Operator ran the two sudo-gated finalization steps. Captured proof:

### Ownership/mode after `sudo chown personal-assistant-svc:users` + `chmod 600`
```
-rw------- 1 personal-assistant-svc users 4151631872 Jul  4 06:23 hb-personal-assistant.sqlite
```
→ owner `personal-assistant-svc:users`, mode `600`. **Matches required end-state.**

### Runtime user identity
```
uid=1028(personal-assistant-svc) gid=100(users) groups=100(users),1023(http)
```
→ `administrators` group **absent** — svc remains demoted (least-privilege), yet owns and can read the DB.

### `sudo -u personal-assistant-svc` read-only SQLite validation
| Check | Result |
|---|---|
| `PRAGMA quick_check` | `ok` |
| `PRAGMA integrity_check` | `ok` |
| schema (`MAX(schema_migrations.version)`) | 98 |
| table count | 506 |

(The earlier `table_count` traceback was a shell-quoting artifact only, resolved with parameterized SQL; no DB issue.)

**Service-user validation: PASS.** No DB recopy occurred; no secrets touched.
