# Findings and Fixes

**STAMP:** 20260701T072640Z

## Finding: Real DB pre-v96

**Real DB/API/UI evidence:** `schema_migrations` at 95; `project_schedule_named_baseline_slots` absent.  
**Fix:** Ran `SQLiteMigrator.apply()` → v96.  
**Files changed:** None (operational migration only).  
**Validation:** `post-migration-db-proof.md`, integrity ok.

## Finding: Driver detail HTTP 401 for slash activity IDs

**Real DB/API/UI evidence:** `GET .../drivers/FAB%2FDEL-10/detail` → 401; `FM-PERMPOWER` → 200 with named context.  
**Fix:** None in Phase 10 (proof used `FM-PERMPOWER`). Route/path encoding limitation documented.  
**Files changed:** None.  
**Validation:** `api-real-driver-current-contract-baseline.json`.

## Code changes

**No application code changes required.** Phase 10 is evidence-only plus real DB migration.
