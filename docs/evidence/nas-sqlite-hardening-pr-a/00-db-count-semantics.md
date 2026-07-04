# PR-A — DB schema-object count semantics

This note accompanies the PR-A SQLite / NAS-runtime hardening change (`feat(nas): P0 sqlite
startup guards, telemetry, and migration policy`). It clarifies a **reporting-semantics
correction**, not a schema change or data loss.

## What changed

`src/hb_assistant/store/db_posture.py::schema_object_counts()` (surfaced by the admin-only
`/api/admin/db/status` endpoint) reports application-object counts by **excluding SQLite
internal catalog objects**:

```sql
SELECT count(*) FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%';  -- table_count
SELECT count(*) FROM sqlite_schema WHERE type = 'view'  AND name NOT LIKE 'sqlite_%';  -- view_count
-- schema_object_count = table_count + view_count
```

## Why 505 vs 506

- `SELECT count(*) FROM sqlite_schema WHERE type='table'` (no `sqlite_%` filter) includes
  SQLite-internal tables such as **`sqlite_sequence`** (created automatically for `AUTOINCREMENT`
  columns). That count is **506**.
- PR-A admin `table_count` intentionally excludes `sqlite_%` internals, so it reports **505**
  application tables.
- Application `view_count` is **2**.
- `schema_object_count` (application tables + views) is therefore **507**.

| Metric | Value | Definition |
|---|---|---|
| all-`type='table'` (historical, includes `sqlite_%`) | **506** | includes `sqlite_sequence` |
| PR-A admin `table_count` (application) | **505** | `type='table'` excluding `sqlite_%` |
| `view_count` | **2** | `type='view'` excluding `sqlite_%` |
| `schema_object_count` | **507** | `table_count` + `view_count` |

Earlier N3 / N4A evidence reported **506** because they counted all non-`sqlite_%`… no —
they counted `type='table'` *without* the PR-A admin helper's `sqlite_%` exclusion, so
`sqlite_sequence` was included. **This is a counting-semantics difference, not schema drift and
not a lost table.** The head schema version remains **98** (see PR-1 `LATEST_SCHEMA_VERSION`).

## Runtime-validation provenance (not carried into this PR)

The PR-A runtime posture was validated **PASS** by a later authorized on-NAS operator smoke. An
earlier *automated* attempt reported FAIL only because the NAS Docker socket requires
**interactive operator sudo** (the agent runs non-sudo) — an operator-path limitation, **not a
runtime defect** in this code. That superseded automated-run evidence and the later operator
smoke bundles are intentionally **not** included in PR-A; this PR carries the hardening code +
tests + this semantics note only. No auth/Graph/N4B/N4C/N5 evidence is imported.
