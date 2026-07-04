# 03 — DB readonly allowlist design

## Tool: `hb_db_select`

Structured inputs only — **no raw SQL**.

| Input | Rule |
|---|---|
| `table_key` | Enum from allowlist registry |
| `columns` | Subset of allowlisted columns; `SELECT *` forbidden |
| `filters` | Equality only on allowlisted columns |
| `order_by` | Allowlisted column or omitted |
| `limit` | Default 25, max 100 |

## Connection

- SQLite URI `file:...?mode=ro`
- `PRAGMA query_only=ON`
- `assert_db_storage_allowed()` before open

## Production posture

**Default-deny.** Proposal-only production entry:

| table_key | table | columns |
|---|---|---|
| `schema_version` | `schema_version` | `version`, `applied_at` |

Requires Bobby approval before enabling additional production tables.

## Test-only allowlist

`nas_mcp_test_items` registered in tests via `register_test_allowlist()`.
