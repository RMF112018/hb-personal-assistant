# Migration-Route Map (origin/main 97efbb6b) — feeds 07 + 11 + NF-ENV-001

Source: `store/migration_authorization.py` (blob a6de75e2), `store/startup_schema_policy.py` (5faecc1b),
`store/migrator.py` (f210fd13), `config/db_storage_guard.py` (432e7e00), `store/database_identity.py` (cb99661a).

## Storage classification (NF-ENV-001 surface)
`DatabaseStorageClass` (db_storage_guard.py:32): MANAGED_PRODUCTION, MANAGED_LOCAL, ISOLATED_WORKSPACE,
READ_ONLY_SNAPSHOT, DISPOSABLE_REHEARSAL, EXPLICIT_DEVELOPMENT, BLOCKED.
`classify_storage_class(db_path)` (:220): **exact-path equality** (`_same_path`, resolve+compare) —
MANAGED_PRODUCTION iff resolved == `nas_default_db_path()`; snapshot/workspace matched by exact path
(RC-2 spoof defense: they share NAS prefix+db-parent+filename with prod, so only exact-path separates
them); managed matched FIRST so a dev/rehearsal path can never shadow prod; else **BLOCKED** (fail-closed).
`describe_opened_database(conn, declared)` (database_identity.py:32): reads `PRAGMA database_list`, takes
the ACTUAL `main` file (declared path is diagnostic only), resolves it, opens a read-only `guard_fd`
(`os.open(..., O_RDONLY)`), captures `st_dev/st_ino`, re-classifies via `classify_storage_class`, and
fails closed (`OpenedDatabaseIdentityUnavailable`) when no main DB is attached.
→ NF-ENV-001 live proof requires mounting the live DB at its REAL path so `nas_default_db_path()` resolves
to it and classification returns MANAGED_PRODUCTION (a probe path like /probe/db.sqlite would classify BLOCKED).

## Routes
| Route | Entry | Capability acquirer | Operator state | Backup receipt | Allowed classes |
|---|---|---|---|---|---|
| A. Startup | launcher/service → forecast_bootstrap `_ensure_managed_database` → `apply_startup_schema_policy` | `acquire_startup_capability()` | the startup-migration enable flag (set) | REQUIRED for MANAGED_PRODUCTION (`require_production_receipt=True`); the startup backup-receipt variable JSON w/ existing non-empty backup | managed |
| B. Admin | `POST /api/admin/schema/migrate` → `admin_schema_migrate` (RBAC `require_admin_role`) | `acquire_admin_capability(role)` (re-checks role["role"]=="admin" — issuer boundary) | admin RBAC header | not required by design (`require_production_receipt=False`) | managed |
| C. One-shot/CLI | CLI `apply()` sites | (ordinary sites converted to read-only `ensure_schema_ready`; managed migration still needs authorization) | n/a | per class | managed |
| D. Local bootstrap | app/CLI entry auto-bootstrap | `acquire_local_bootstrap_capability()` | none | none | **MANAGED_LOCAL only** (can never target NAS prod/snapshot/workspace) |

## Enforcement pipeline (every managed apply)
1. `authorize_migration(capability, resolved_path, expected_origin_version, target_version)` (:356):
   `classify_storage_class(resolved)`; reject if not managed; reject if class ∉ `capability.allowed_storage_classes`;
   MANAGED_PRODUCTION + `require_production_receipt` ⇒ backup receipt required to mint authorization.
2. `apply()` → `describe_opened_database` (opened identity + guard FD).
3. `validate_authorization(authorization, opened, require_backup_receipt)` (:440) BEFORE any DDL:
   READ_ONLY_SNAPSHOT ⇒ always denied; BLOCKED ⇒ denied; `authorization.storage_class == opened.storage_class`;
   `target_identity.storage_class` match; **device/inode == opened** (substitution = hard fail);
   MANAGED_PRODUCTION + require_backup_receipt ⇒ receipt enforced.
4. Borrowed conn already in transaction ⇒ refused (RC-3).
5. `assert_origin_version(authorization, origin)` ⇒ replay defense (reused authorization whose
   `expected_origin_version` no longer matches actual MAX(version) fails).
6. Single `with transaction(conn)` runs V1..V127; `revalidate_opened_identity(opened)` before commit.
7. Audit events `migration_started/rejected/completed` (sanitized).

## Route selection for THIS deployment (evidence-only recommendation, not an approval)
- The operator route for a NAS V124→V127 migration is **Route A (startup)** with the startup-migration enable flag (set)
  + a valid the startup backup-receipt variable referencing a real non-empty pre-migration backup, OR
  **Route B (admin)** via an authenticated admin call. Route D cannot target production (MANAGED_LOCAL only).
- Rehearsal (Stage 3) exercises Route A end-to-end against an isolated production-derived V124 copy
  (the copy classifies DISPOSABLE_REHEARSAL, so it is authorized via a rehearsal-scoped capability, not a
  production one — documented deviation: the exact production capability requires MANAGED_PRODUCTION path
  identity which only the real NAS path yields; rehearsal proves the same code path + receipt gating).
