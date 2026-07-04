# 06 — Validate DB proof

## Command

```sh
sudo sh scripts/validate-db.sh
```

## Result: PASS

| Check | Expected | Observed |
|---|---|---|
| `quick_check` | ok | **ok** |
| schema | 98 | **98** |
| `table_count` | 505 | **505** |
| `view_count` | 2 | **2** |
| `schema_object_count` | 507 | **507** |
| owner | personal-assistant-svc:users | **yes** |
| mode | 600 | **-rw-------** (600) |

Read-only URI connection only — no migrations, no writes.

Captured: `captured/evidence/validate-db.txt`

## Note

Script emitted cosmetic `WARN: expected mode 600` despite `-rw-------` in `file_stat` (case-pattern mismatch). Actual mode is correct.
