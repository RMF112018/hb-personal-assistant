# 09 — DB Post-Smoke Validation

Read-only validation as `personal-assistant-svc` against N3 final DB path.

## DB truth (authoritative)

| Field | Value |
|---|---|
| Path | `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite` |
| Owner/mode | `personal-assistant-svc:users`, **600** |
| `PRAGMA quick_check` | **ok** |
| Schema `MAX(version)` | **98** |
| Table count (`sqlite_schema` type=table) | **506** |

**Final table count matches N3 baseline (506).**

## Runtime vs DB-truth discrepancy

During smoke, `GET /api/admin/schema/status` reported `table_count=507` (counts `sqlite_master` tables **and views** per admin helper). Post-smoke read-only SQLite DB-truth query returned **506** tables.

**Classification:** Documented runtime/API count discrepancy — **not** persisted schema drift. Schema version remained **98**; no new `schema_migrations` rows; no new production tables.

## Integrity

No `integrity_check` failure. No evidence of destructive migration beyond expected bootstrap dir/config side effects under app-support (outside DB file).
