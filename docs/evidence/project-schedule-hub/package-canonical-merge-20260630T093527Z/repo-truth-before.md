# Repo Truth Before

- Schedule import preview/commit entrypoint: `src/hb_assistant/construction/analytics/schedule_import_service.py`.
- ZIP parsing already ignored `__MACOSX`, AppleDouble `._*`, dotfiles, directories, nested archives, unsafe paths, and oversized decompressed packages.
- XER parsing entrypoint: `schedule_xer_parser.py`; XER activity key is `TASK.task_code`, source object id is `TASK.task_id`.
- XML parsing entrypoint: `schedule_xml_parser.py`; hierarchy-aware `parse_pmxml_package_bytes()` separates XML current `<Project>` from `<BaselineProject>` entities.
- Package equivalence/assembly entrypoint before implementation: `schedule_package_assembly.py`.
- Existing package evidence tables: `schedule_import_packages`, `schedule_import_package_files`, `schedule_source_capabilities`, `schedule_package_field_lineage`, `schedule_package_equivalence_facts`.
- Existing baseline evidence tables: `schedule_baseline_projects`, `schedule_baseline_activities`, `schedule_baseline_relationships`, `schedule_baseline_wbs`, `schedule_baseline_activity_codes`, `schedule_baseline_udfs`, `schedule_baseline_activity_crosswalk`, `schedule_baseline_health_facts`.
- Existing current analytical tables: `procore_ep_schedule_activities`, `procore_ep_schedule_relationships`, `procore_ep_schedule_activity_code_assignments`, `procore_ep_schedule_udf_values`.
- Current behavior before implementation selected XER as primary and used companion XML only additively for codes/UDFs; TWNU current activities and relationships stayed correct, but codes/UDFs doubled to 9,990 / 8,622.
- CPM recompute is triggered after commit by `ScheduleCpmRecomputeService.recompute(version_key)` and already runs the full CPM chain.

## Pre-change real fixture observations

- `TWNU18.zip`: XER current 1,378 activities / 3,718 relationships / 5,171 codes / 4,311 UDFs; XML current 1,378 activities / 3,718 relationships / 5,171 codes / 4,311 UDFs; XML baselines 1,177/2,658 and 1,420/3,780.
- `TWNU19.zip`: XER current 1,507 activities / 3,921 relationships / 5,171 codes / 4,311 UDFs; XML current 1,507 activities / 3,921 relationships / 5,171 codes / 4,311 UDFs; XML baselines 1,177/2,658 and 1,378/3,718.
- XER `task_id` and XML `Activity.ObjectId` match for sampled current activities.
- Relationship overlap needed relationship-type alias normalization (`FS` vs `Finish to Start`, etc.).
