# Post-Migration DB Proof

**STAMP:** 20260701T072640Z  
**Proof type:** real local DB

## Migration command

```python
SQLiteMigrator(db_path=HB_ASSISTANT_DB_PATH).apply()
```

## Results

| Metric | Before | After |
|--------|--------|-------|
| schema_migrations MAX(version) | 95 | **96** |
| v96 name | — | `v96_project_schedule_named_baseline_slots` |

## Named slots table

`project_schedule_named_baseline_slots` — **PRESENT**

Columns: selection_id, project_key, slot_key, schedule_version_key, display_name, notes, selected_by, selected_at, created_at, updated_at, is_active

## Integrity

`PRAGMA integrity_check` → **ok**

## Errors

None.
