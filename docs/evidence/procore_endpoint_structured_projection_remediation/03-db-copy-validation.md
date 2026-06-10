# 03 — DB-Copy Validation

All projection validation was performed on a `/tmp` copy of the production SQLite DB.
The production DB was never mutated by the validation steps.

## Production DB
- Path source: `PathPolicy().get_db_path()` (the PLAIN app-support root).
- sha256 **before** validation: `a24b6ab15982fa71ba951a54d1aaeead0a4e4f910f126150bec6ef1a4ac3a8f2`
- sha256 **after** validation:  `a24b6ab15982fa71ba951a54d1aaeead0a4e4f910f126150bec6ef1a4ac3a8f2`
- **Result: UNCHANGED across validation ✓**

## Validation procedure (on `/tmp` copy)
1. `sqlite3 .backup` copy of production DB to `/tmp`.
2. Applied migrations → schema head **47** (idempotent; re-apply stays 47).
3. Dropped the copy's `procore_ep_*` tables and re-migrated so the schema matches the
   regenerated registry exactly (recreate, not alter).
4. `projection-inventory` → 37 endpoints, 2,439 distinct paths.
5. `projection-reprocess --apply` (enforce mode) → primary_written **10,105**,
   child_written **22,089**, degraded **0**.
6. `projection-audit` → `ok = true`, `unmapped_primary_business_fields = 0`,
   `unmapped_nested_business_fields = 0`, `unknown_business_field_paths = 0`.
7. `external_writeback_performed` violations across all `procore_ep_*` tables: **0**.
8. All projected rows carry `raw_payload_id` linkage back to
   `procore_endpoint_raw_payloads`.

## Disclosure — inadvertent production daily-refresh during diagnosis
While diagnosing a scheduler test, the `daily-source-refresh` orchestrator was run once
outside the pytest isolation harness. In production config this performs the normal daily
behavior: it auto-migrated the production DB to V47 and ran a live Procore sync (additive,
non-destructive — the same operation the scheduled job performs daily). This advanced the
production DB to the post-merge end state ahead of merge. It introduced no data loss and
no external writeback. All projection validation proper (steps 1–8) was then performed on
`/tmp` copies, and the production sha256 is proven unchanged across those validation steps.
A memory note was recorded to prevent re-running the orchestrator outside isolation.

## No production mutation by the package code paths
The new `projection-reprocess --apply` command refuses to run without an explicit `--db`,
so it can never default to the production DB. The projection engine performs no live
Procore calls and no external writeback (`external_writeback_performed CHECK = 0` on every
new table).
