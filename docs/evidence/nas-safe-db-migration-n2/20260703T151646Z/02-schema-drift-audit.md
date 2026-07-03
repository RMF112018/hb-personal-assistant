# N2 · 02 — Repo-Truth Schema-Drift Audit

Timestamp (UTC): 20260703T151646Z · Method: static repo read + empirical scratch-DB migration.

## Headline

**Confirmed drift.** The migrator defines, applies, and records a **v98** migration, but the
single-source-of-truth constant `LATEST_SCHEMA_VERSION` remained **97**. `apply()` and
`current_version()` both return `MAX(version) FROM schema_migrations` = **98** on any migrated DB, so
the recorded head disagreed with the constant. `/health` masked it with `>=`; strict-equality
surfaces and ~13 test files were broken by it.

### Empirical confirmation (pre-fix, scratch DB)

```
LATEST_SCHEMA_VERSION (constant) = 97
apply() landed version           = 98
MAX(schema_migrations.version)   = 98
v98 row                          = (98, 'v98_project_schedule_review_dispositions')
DRIFT (apply != constant)        = True
```

## Ten audit questions

1. **Where is `LATEST_SCHEMA_VERSION` defined?** `src/hb_assistant/store/migrator.py:17` (`= 97`, pre-fix).
2. **Highest migration actually applied?** **v98** (`v98_project_schedule_review_dispositions`); apply block `migrator.py:8631-8639`; SQL body `store/project_schedule_review_disposition_tables.py` (`V98_STATEMENTS`). No v99.
3. **How is the applied version recorded?** No `PRAGMA user_version`. A `schema_migrations` table (created `migrator.py:143-145`); each migration `INSERT`s a `(version,name,applied_at)` row; `apply()` and `current_version()` (`migrator.py:9330-9339`) return `MAX(version)`.
4. **How does `/health` compute the fields?** `api.py:830-837`: `schema_version = current_version()`; `schema_expected = LATEST_SCHEMA_VERSION`; `schema_ready = schema_version >= LATEST_SCHEMA_VERSION`. The **`>=`** masks a head that is ahead of the constant. Admin schema endpoints `api.py:3117-3139` use the same `>=`.
5. **Do tests assert `97`?** **No literal `97` anywhere.** Tests assert `apply()/current_version()/report.schema_version == LATEST_SCHEMA_VERSION`, so the drift **broke** them (98 ≠ 97). Representative breakers: `test_phase_10_schema.py:55-56,156`, `test_migrator_v76_project_staffing.py:30-32`, `test_phase_09_schema_status.py:49`, `test_migrator_v61_external_forecasts.py:53-54`, `test_data_quality_schema_v22.py`, `test_graph_files_drive_item_indexing.py:178`, `test_procore_endpoint_structured_projection_remediation.py:782`, and others. Bumping the constant to 98 **repairs all of them** (no test edits needed).
6. **Docs/scaffold references stale?** `docs/implementation/project-schedule-controls/baseline-repo-truth.md:140` says `LATEST_SCHEMA_VERSION = 94` — **separately stale** (predates both 97 and 98). Per operator instruction this is **noted only, not edited** in N2. No `deploy/` runbook pins 97/98.
7. **Is v98 idempotent?** Not intrinsically — it is a destructive rebuild-and-rename (`CREATE …_v98` / `INSERT…SELECT` / `DROP` / `RENAME`, no `IF [NOT] EXISTS` on the tables; only indexes guard). It is safe **only** via the outer `WHERE version = 98` schema_migrations guard (`migrator.py:8632`). Re-running `apply()` is a correct no-op (verified in tests); re-running the raw statements alone would fail. This is acceptable as written but is the exact reason the guard test pins double-`apply()`.
8. **Does fixing require migration-code changes?** **No.** Only the constant needs bumping (97→98). Migration semantics are untouched.
9. **Can a real DB at 97 safely migrate to 98?** N/A for any DB the migrator produces — the migrator already lands DBs at 98 (there is no on-disk "97" head the migrator can create; v98 always applies). A pre-existing DB missing the v98 row would gain it on next `apply()` via the additive, guarded block. **No live/production DB was opened or migrated in N2.**
10. **Is auto-migrate-on-open a hazard for copied-DB smoke?** Yes, to be planned around. `construction/store/repositories.py:30-35` calls `SQLiteMigrator(db_path).apply()` on first use; other call sites: `source_refresh/orchestrator.py`, `procore/live_sync.py`, CLI entrypoints. Any repository/CLI/app touch migrates the DB to head — so a copied-DB smoke that instantiates a repository **will write** the v98 migration into the copy. The copied-DB smoke plan (`07`) treats this as an expected, explicitly-allowed migration and gates on it.

## Masking vs. exposing surfaces

- **Masks** the drift: `/health` (`>=`, `api.py:837`).
- **Exposes** the drift (strict `==`): `construction/second_brain/automation_health.py:128-131` returned degraded `v98!=v97`; and every equality test in Q5.

## Fix direction (applied — see `03`)

Bump `migrator.py:17` `LATEST_SCHEMA_VERSION` `97 → 98`. One line. No test edits, no doc edits.
