# 07 — Schema Version Validation

## Repo-truth mechanism

- Constant: `src/hb_assistant/store/migrator.py:17` → `LATEST_SCHEMA_VERSION = 98` (this branch).
- Applied version stored in the DB's `schema_migrations` table (`migrator.py:145-150`).
- Canonical reader (reused, not hand-rolled SQL): `SQLiteMigrator(db_path).current_version()` → `MAX(version)` from `schema_migrations` (`migrator.py:9330`).

## Results

| DB | `current_version()` | `MAX(schema_migrations.version)` | == 98 |
|---|---|---|---|
| Live source (read-only) | 98 | — | ✔ |
| Local copy | 98 | 98 | ✔ |
| NAS copy | *pending Step 6* | *pending* | *pending* |

Local and source schema heads both equal `LATEST_SCHEMA_VERSION` (98). **Schema validation PASS on both local artifacts.** NAS-side confirmation deferred to service-user validation (blocked — see 01/05).

Caveat for future readers: `main` (unmerged) still carries the stale `LATEST_SCHEMA_VERSION = 97` while the migrator applies/records 98. This N3 work runs on the branch where the constant is correctly 98, so equality holds. Do not run equality checks against a `main`-derived constant.
