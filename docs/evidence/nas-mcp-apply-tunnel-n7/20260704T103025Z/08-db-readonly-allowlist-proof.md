# 08 — DB readonly allowlist proof

## Apply-time result (WARN)

```text
hb_db_select table_key=schema_version columns=[version,applied_at] limit=3
```

**Allowlist gate:** PASS (key accepted)  
**Query result at apply time:** `no such table: schema_version` — code mapped tool key to table name `schema_version`; production DB uses `schema_migrations`.

## Deny proof (PASS)

```text
table_key=secrets → table_key not allowlisted: secrets
```

## DB file (PASS)

mtime/size unchanged preflight → final (see `05`).

## Approved allowlist decision (post-apply, Bobby)

| Item | Decision |
|---|---|
| MCP tool key | **`schema_version`** (unchanged) |
| Internal production mapping | **`schema_migrations`** table only |
| Approved columns | `version`, `name`, `applied_at` only |
| Other production tables | **Not approved** |

Implementation of the mapping and bounded DB MCP re-proof are **deferred** — may close DB WARN later.

Captured probe: `captured/mcp-tunnel-probe.jsonl` (`db_select_schema_version`, `db_deny_secrets`).
