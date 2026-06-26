# Schema Migration

## Repo-Truth Maximum

V74 was present before edits:

- `src/hb_assistant/store/migrator.py`: `LATEST_SCHEMA_VERSION = 74`
- `src/hb_assistant/store/forecast_output_matrix_tables.py`: V74 forecast monthly-matrix DDL
- `src/hb_assistant/store/migrator.py`: schema row insert for `v74_forecast_monthly_matrix`

## V75 Additions

New additive table module:

- `src/hb_assistant/store/schedule_import_health_tables.py`

New V75 tables:

- `schedule_import_packages`
- `schedule_import_package_files`
- `schedule_source_capabilities`
- `schedule_baseline_projects`
- `schedule_baseline_activities`
- `schedule_baseline_relationships`
- `schedule_baseline_wbs`
- `schedule_baseline_activity_codes`
- `schedule_baseline_udfs`
- `schedule_baseline_activity_crosswalk`
- `schedule_baseline_health_facts`
- `schedule_version_diff_facts`

## Collision Rationale

V74 is forecast-owned. This remediation uses V75 because the selected base already had V74 and no V75 migration existed. The lifecycle contract table count was updated from `439` to `451`.
