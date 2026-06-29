# Phase 8B UDF Normalization Repo Truth

## 1. Current Branch, HEAD, and Working-Tree Status

- Branch: detached HEAD
- HEAD: `9e76158a7861b92a0670d782790da03d210e0e99`
- Working tree: Phase 5–8A schedule-controls work present (visualization contracts, trend aggregation, selected baseline, PM UI). Phase 8B adds UDF normalization on top without altering Phase 8A semantics.

## 2. Relevant Files, Services, Routes, and Tests

| Area | Path |
|------|------|
| UDF normalization service | `src/hb_assistant/construction/analytics/project_schedule_udf_normalization_service.py` |
| Visualization metric contracts | `src/hb_assistant/construction/analytics/project_schedule_visualization_metric_contract.py` |
| Trend aggregation | `src/hb_assistant/construction/analytics/project_schedule_trend_aggregation_service.py` |
| Selected baseline (8A) | `src/hb_assistant/construction/analytics/project_schedule_selected_baseline_service.py` |
| API routes | `src/hb_assistant/construction/analytics/api.py` (`GET /schedule/metrics/{metric_key}/trend`, `GET /schedule/metrics/trends`) |
| Raw UDF reads | `src/hb_assistant/store/schedule_activity_repository.py` (`list_udf_values`) |
| UDF schema | `src/hb_assistant/store/schedule_tables.py` (V62) |
| Import commit | `src/hb_assistant/construction/analytics/schedule_import_service.py` |
| XML/XER parsers | `schedule_xml_parser.py`, `schedule_xer_parser.py` |
| Phase 8B tests | `tests/test_project_schedule_udf_normalization.py` |
| Regression tests | `tests/test_project_schedule_visualization_metric_contract.py`, `tests/test_project_schedule_trend_aggregation_api.py`, `tests/test_project_schedule_baseline_selection.py` |

## 3. Existing UDF Source Tables and Columns

### Current schedule UDFs — `procore_ep_schedule_udf_values` (V62)

| Column | Purpose |
|--------|---------|
| `id` | Surrogate key |
| `project_key` | Construction project |
| `schedule_table_id` | Schedule table identity |
| `schedule_id` | Schedule identity within project |
| `schedule_version_key` | Committed version key |
| `import_id` | FK to `schedule_file_imports` |
| `activity_id` | Activity key within version |
| `udf_type_name` | P6 UDF field name |
| `udf_data_type` | Source type (Text, FinishDate, etc.) |
| `udf_value` | All values stored as TEXT |
| `source_object_id` | Primavera ObjectId / UDF type id |

### Baseline UDF evidence — `schedule_baseline_udfs` (V75)

Separate baseline evidence store (`baseline_project_key`, `activity_id`, `udf_type_name`, `udf_data_type`, `udf_value`, `source_object_id`). Phase 8B normalization targets current schedule UDFs; baseline UDFs remain import evidence only.

## 4. How UDF Names Are Stored

- One row per `(activity_id, udf_type_name)` in the EAV table.
- Names are stored exactly as exported from P6 (e.g. `PHASE`, `Filter Out`, `Start (Previous Status)`).
- No normalized name column exists today; Phase 8B maps names at read time via a deterministic alias registry.

## 5. How UDF Values Are Stored

- All values coerced to `udf_value TEXT` at import.
- `udf_data_type` preserves source typing metadata.
- Parsed from PMXML (`TextValue`, `FinishDateValue`, etc.) or XER (`udf_text`, `udf_number`, `udf_date`).

## 6. How UDF Records Reference Entities

| Reference | Column |
|-----------|--------|
| Project | `project_key` |
| Schedule version | `schedule_version_key` |
| Activity | `activity_id` (joins to `procore_ep_schedule_activities`) |
| Object id | `source_object_id` on UDF row |
| Import package/file | `import_id` → `schedule_file_imports` |
| Source schedule identity | Indirect via `schedule_version_identity_matches` / `schedule_identities` |

Activity code is not stored on UDF rows; join is via `activity_id` within the same `schedule_version_key`.

## 7. Normalization During Import

UDFs are **not** normalized during import. Import pipeline: parse → package merge → preview → commit → `bulk_insert_table("procore_ep_schedule_udf_values", ...)`. Generic EAV storage only.

## 8. Deterministic Join to Schedule Activities

Join key: `(schedule_version_key, activity_id)` between `procore_ep_schedule_udf_values` and `procore_ep_schedule_activities`.

Phase 8B `get_udf_join_proof()` reports join success rate, orphan UDF rows, and activities without UDF coverage.

## 9. UDF Aliases for the Same Intended Field

| Internal field | Raw name aliases (priority order) |
|----------------|-----------------------------------|
| `old_id` | `OLD ID` |
| `phase` | `PHASE` |
| `floor` | `FLOOR` |
| `sector_area` | `SECTOR / AREA` |
| `subcontractor` | `SUBCONTRACTOR` |
| `cost_code` | `Cost Code` |
| `filter_out` | `Filter Out` |
| `start_previous_status` | `Start (Previous Status)`, `Start Previous Status` |
| `finish_previous_status` | `Finish (Previous Status)`, `Finish Previous Status` |
| `update_notes_1` | `Update Notes - 1` |
| `update_notes_2` | `Update Notes - 2` |
| `update_notes` | `Update Notes` (coalesce with `- 1` / `- 2` fallbacks) |
| `schedule_review_comments` | `Schedule Review Comments` |

Duplicate rows for the same `(activity_id, udf_type_name)` are flagged ambiguous; values are not silently collapsed.

## 10. Migration Required?

**No.** Read-through normalization is sufficient. Generic EAV storage has deterministic join keys.

## 11. Backfill Required?

**No.** Existing imported UDF rows are read at query time. No destructive updates to raw data.

## 12. Phase 8B Implementation Approach

**Read-through normalization service only** (no materialized normalized table).

- `ProjectScheduleUdfNormalizationService` queries `procore_ep_schedule_udf_values` and joins activities on read.
- Raw UDF values preserved in `raw_udf_sources` metadata on normalized records.
- Metric payloads built backend-side and exposed via existing Phase 6 trend routes (`READINESS_AWARE_TREND_METRICS`).

## 13. UDF-Dependent Metric Readiness Before Phase 8B

| Metric | Readiness | Blockers |
|--------|-----------|----------|
| `delay_analysis` | `ready_after_udf_normalization` | Named UDF normalization not proven; trend API not implemented |
| `window_start_accuracy` | `ready_after_udf_normalization` | UDF filters/status not normalized; window API not implemented |
| `window_finish_accuracy` | `ready_after_udf_normalization` | Same |
| `should_have_finished_status` | `ready_after_udf_normalization` | UDF filters/comments not normalized; donut API not implemented |
| `critical_issues_category_model` | `ready_after_udf_normalization` | UDF comments/ownership not normalized; panel API not implemented |

All five return `metric_not_trend_ready` (422) from trend endpoints before Phase 8B.

## 14. Explicit Non-Scope Confirmation

- No Phase 8C review workbench expansion
- No selected-baseline recompute
- No import pipeline rewrite
- No causation, responsibility, entitlement, or compensability logic
- No frontend formula computation
- No cost-weighted defaults
- No fabrication of UDF values
