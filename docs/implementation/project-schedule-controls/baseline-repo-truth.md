# Project Schedule Controls Baseline Repo Truth

## 1. Branch, HEAD, Status

- Branch: `feat/obsidian-mcp-llm-chat-memory`
- HEAD: `76879f374da1942bf8121e31102b09e4b339fa24`
- Repo-local `AGENTS.md`: none found under `/Users/bobbyfetting/hb-personal-assistant`.
- Working tree at baseline capture: no tracked modifications; untracked evidence only:
  - `docs/evidence/project-schedule-hub/schedule-data-capability-audit-20260629T075754-0400.zip`
  - `docs/evidence/project-schedule-hub/schedule-data-capability-audit-20260629T075754-0400/`

## 2. Existing Schedule Backend Files

Project hub and schedule-control services:

- `src/hb_assistant/construction/analytics/project_schedule_summary_service.py`
- `src/hb_assistant/construction/analytics/project_schedule_comparison.py`
- `src/hb_assistant/construction/analytics/project_schedule_drilldown_service.py`
- `src/hb_assistant/construction/analytics/project_schedule_driver_analysis_service.py`
- `src/hb_assistant/construction/analytics/project_schedule_review_service.py`
- `src/hb_assistant/construction/analytics/project_schedule_memo_service.py`
- `src/hb_assistant/construction/analytics/project_schedule_narrative_qa.py`
- `src/hb_assistant/construction/analytics/project_schedule_import_pipeline_service.py`

Schedule import, parser, identity, quality, CPM, and diff services:

- `src/hb_assistant/construction/analytics/schedule_import_service.py`
- `src/hb_assistant/construction/analytics/schedule_file_parser.py`
- `src/hb_assistant/construction/analytics/schedule_xer_parser.py`
- `src/hb_assistant/construction/analytics/schedule_xml_parser.py`
- `src/hb_assistant/construction/analytics/schedule_msp_xml_parser.py`
- `src/hb_assistant/construction/analytics/schedule_csv_parser.py`
- `src/hb_assistant/construction/analytics/schedule_trust_service.py`
- `src/hb_assistant/construction/analytics/schedule_quality_service.py`
- `src/hb_assistant/construction/analytics/schedule_quality_engine.py`
- `src/hb_assistant/construction/analytics/schedule_quality_worker.py`
- `src/hb_assistant/construction/analytics/schedule_cpm_*`
- `src/hb_assistant/construction/analytics/schedule_graph.py`
- `src/hb_assistant/construction/analytics/schedule_version_diff.py`
- `src/hb_assistant/construction/analytics/schedule_diff_intelligence.py`

Store, repository, and table modules:

- `src/hb_assistant/store/project_schedule_hub_repository.py`
- `src/hb_assistant/store/project_schedule_hub_tables.py`
- `src/hb_assistant/store/schedule_tables.py`
- `src/hb_assistant/store/schedule_import_health_tables.py`
- `src/hb_assistant/store/schedule_identity_tables.py`
- `src/hb_assistant/store/schedule_quality_tables.py`
- `src/hb_assistant/store/schedule_cpm_tables.py`
- `src/hb_assistant/store/schedule_diff_detail_tables.py`
- `src/hb_assistant/store/schedule_diff_impact_tables.py`

## 3. Existing Frontend Files

Project Schedule Hub:

- `frontend/src/pages/ProjectSchedulePage.tsx`
- `frontend/src/pages/ProjectScheduleWorkbenchPage.tsx`
- `frontend/src/pages/ProjectScheduleDriverDetailPage.tsx`
- `frontend/src/pages/ProjectScheduleImportPage.tsx`
- `frontend/src/components/projects/ProjectScheduleDashboardVisualizations.tsx`
- `frontend/src/components/projects/projectScheduleDashboardData.ts`

Standalone schedule surfaces:

- `frontend/src/pages/ScheduleQualityPage.tsx`
- `frontend/src/pages/ScheduleCpmPage.tsx`
- `frontend/src/pages/ScheduleVersionDiffPage.tsx`
- `frontend/src/pages/ScheduleIdentityReviewPage.tsx`
- `frontend/src/pages/ScheduleImportsPage.tsx`
- `frontend/src/pages/ScheduleVersionsPage.tsx`
- `frontend/src/pages/ScheduleActivitiesPage.tsx`
- `frontend/src/components/schedule/**`

API client functions exist in `frontend/src/lib/api.ts` for:

- Project schedule summary
- Drilldowns
- Drivers
- Driver detail
- Baseline get and put
- Review item get, sync, and patch
- Export download

## 4. Existing API Routes

Project-scoped schedule routes in `src/hb_assistant/construction/analytics/api.py`:

- `GET /api/projects/{project_key}/schedule`
- `GET /api/projects/{project_key}/schedule/drilldowns?type=&limit=&offset=&as_of=`
- `GET /api/projects/{project_key}/schedule/drivers?type=&limit=&offset=&driver_activity_id=&as_of=`
- `GET /api/projects/{project_key}/schedule/drivers/{activity_id}/detail?comparison_basis=&as_of=`
- `GET /api/projects/{project_key}/schedule/review-items?review_status=&limit=&offset=&as_of=&comparison_basis=`
- `POST /api/projects/{project_key}/schedule/review-items?as_of=`
- `PATCH /api/projects/{project_key}/schedule/review-items/{review_item_id}`
- `GET /api/projects/{project_key}/schedule/export?format=&as_of=&variant=&scope=&include_persisted_review=`
- `GET /api/projects/{project_key}/schedule/baseline`
- `PUT /api/projects/{project_key}/schedule/baseline`
- `POST /api/projects/{project_key}/schedule/import-preview`
- `POST /api/projects/{project_key}/schedule/import-commit`
- `GET /api/projects/{project_key}/schedule/imports/{import_id}/status`
- `POST /api/projects/{project_key}/schedule/imports/{import_id}/recompute-cpm`

Standalone schedule routes include:

- `GET /api/schedules/versions/{schedule_version_key}/health-data`
- Quality summary, findings, metrics, rerun, and run detail routes
- CPM summary, activities, longest-path, and diagnostics routes
- Identity review and identity manual action routes
- Import preview and commit routes
- Version, activity, and relationship read routes

## 5. Auth and Operator Requirements

- All routes use `X-HB-UI-Role`; default is `viewer`.
- Allowed local UI roles are `viewer`, `operator`, and `admin`.
- Invalid role returns `403 invalid_ui_role`.
- `require_operator_role` allows only `operator` or `admin`; otherwise it returns `403 operator_role_required`.
- Viewer-readable project schedule routes:
  - Hub summary
  - Drilldowns
  - Drivers
  - Driver detail
  - Review-items GET
  - Export GET
  - Baseline GET
  - Import status GET
- Operator-gated project schedule routes:
  - Review-items POST sync
  - Review-item PATCH
  - Baseline PUT
  - Import preview
  - Import commit
  - Recompute CPM
- Standalone mutating schedule routes such as quality rerun, identity reassignment/split/merge, series membership, and import commit/preview are operator-gated.

## 6. Tables and Migrations

- `LATEST_SCHEMA_VERSION = 94`.
- Schedule-control migration lineage:
  - v62 schedule intelligence, activity, relationship, WBS, calendar, import, and diff foundations.
  - v64 schedule quality runs, metrics, and scorecards.
  - v65-v71 float, source critical-path, quality supplemental, and source-export refinements.
  - v75 schedule import health, packages, baselines, capabilities, and diff facts.
  - v77-v78 schedule identity and manual actions.
  - v79-v80 diff detail facts and impact rollups.
  - v83-v88 CPM diagnostics, forward/backward pass, float, longest path, and criticality.
  - v89 schedule quality app-CPM status.
  - v90 project schedule series membership and baseline selections.
  - v91 project schedule review items.
  - v92 project schedule review item events.

Temporary migrated v94 schema inspection confirmed the schedule tables below exist:

- `schedule_file_imports`
- `procore_ep_schedule_activities`
- `procore_ep_schedule_relationships`
- `procore_ep_schedule_wbs_nodes`
- `procore_ep_schedule_calendars`
- `procore_ep_schedule_activity_code_assignments`
- `procore_ep_schedule_udf_values`
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
- `schedule_version_diffs`
- `schedule_version_diff_facts`
- `schedule_version_diff_detail_facts`
- `schedule_version_diff_impact_rollups`
- `schedule_quality_evaluation_runs`
- `schedule_quality_findings`
- `schedule_quality_metric_results`
- `schedule_quality_scorecards`
- `schedule_cpm_runs`
- `schedule_cpm_activity_results`
- `schedule_cpm_relationship_results`
- `schedule_cpm_diagnostics`
- `schedule_cpm_paths`
- `schedule_cpm_path_activities`
- `schedule_identities`
- `schedule_version_identity_matches`
- `schedule_identity_manual_actions`
- `project_schedule_series_membership`
- `project_schedule_baseline_selections`
- `project_schedule_review_items`
- `project_schedule_review_item_events`

## 7. Existing Relevant Tests

- Project hub/API: `tests/test_project_schedule_hub_api.py`
- Drilldowns/drivers: `tests/test_project_schedule_hub_drilldowns.py`, `tests/test_project_schedule_driver_analysis.py`
- Review workbench/export/driver detail: `tests/test_project_schedule_review_workbench.py`
- Baseline: `tests/test_project_schedule_baseline_selection.py`
- Import pipeline/CPM trigger: `tests/test_project_schedule_import_pipeline.py`
- CPM:
  - `tests/test_schedule_cpm_api.py`
  - `tests/test_schedule_cpm_criticality.py`
  - `tests/test_schedule_cpm_longest_path.py`
  - `tests/test_schedule_health_cpm_aggregation.py`
- Quality:
  - `tests/test_schedule_quality_api.py`
  - `tests/test_schedule_quality_engine.py`
  - Schedule quality migration tests
- Diff/identity/trust:
  - `tests/test_schedule_version_diff.py`
  - `tests/test_schedule_diff_intelligence.py`
  - `tests/test_schedule_identity_review_api.py`
  - `tests/test_schedule_trust_resolver.py`
- Frontend:
  - `frontend/src/pages/ProjectSchedulePage.test.tsx`
  - `frontend/src/pages/ProjectScheduleWorkbenchPage.test.tsx`
  - `frontend/src/pages/ProjectScheduleImportPage.test.tsx`
  - `frontend/src/pages/ScheduleQualityPage.test.tsx`
  - `frontend/src/pages/ScheduleCpmPage.test.tsx`
  - `frontend/src/pages/ScheduleVersionDiffPage.test.tsx`
  - `frontend/src/pages/ScheduleIdentityReviewPage.test.tsx`
  - `frontend/src/pages/ScheduleRoutes.test.tsx`

## 8. Current Metric Sources

- Remaining work: `ProjectScheduleSummaryService._activity_summary`, count of unfinished `procore_ep_schedule_activities`.
- Remaining later, remaining earlier, finish changed, new remaining, worsened float, improved float, and moved remaining milestones: `ProjectScheduleComparisonService.compare_versions`, using unfinished current activities joined by `activity_id` to prior or baseline.
- Comparison finish basis: `remaining_finish`, fallback `finish_date`, fallback `remaining_early_finish`.
- Source/export negative float and zero/near source float: `_activity_summary` and `_remaining_health`, reading source/derived/explicit float columns on `procore_ep_schedule_activities`.
- Computed CPM critical and near-critical: `_computed_cpm`, counting unfinished activities in the selected persisted `schedule_cpm_activity_results` run with `computed_critical_flag` and `computed_near_critical_flag`.
- Forecast finish: `_forecast_finish`, max resolved finish over unfinished current activities.
- Remaining milestones and moved milestones: `_milestones` plus comparison movement.
- Baseline comparison: `_baseline_summary`, `project_schedule_baseline_selections`, `schedule_baseline_*`, and `ProjectScheduleComparisonService`.
- Readiness and identity: `ScheduleTrustService`, `schedule_version_identity_matches`, and `project_schedule_series_membership`.

## 9. Why API and Direct DB Evidence Diverged

- Current canonical logic is service-layer logic, not raw SQL-only logic. It resolves current and previous versions through schedule identity and series trust, filters future-dated imports, and applies comparison eligibility.
- Movement uses resolved finish dates: `remaining_finish` when populated, then `finish_date`, then `remaining_early_finish`. A direct collector that compares only `remaining_finish` can show zero movement when `finish_date` proves movement.
- Computed CPM counts come from persisted CPM run/result rows and must be scoped to the selected run and unfinished activities. Counting source `is_critical` or querying CPM tables without run selection can diverge.
- Source/export float and application-computed CPM float are intentionally separate. Mixing them changes negative, critical, and near-critical counts.
- Driver, workbench, and drilldown route failures in old evidence likely reflected missing role headers or stale route contracts. Current repo has viewer-readable GET routes and operator-gated mutations. Drivers currently require `type`; some driver drilldown types also require `driver_activity_id`.

## 10. Proven Implementation Deltas

- Add `as_of` support to `GET /api/projects/{project_key}/schedule` and `frontend/src/lib/api.ts::getProjectScheduleSummary`; current service supports `as_of`, but the route/client do not pass it.
- Add or harden route contract tests for documented `type` values, missing `type`, missing `driver_activity_id`, invalid `as_of`, and unsupported export format.
- Add a canonical metrics contract module or explicit shared adapter so hub, drilldowns, exports, and evidence collectors do not duplicate metric SQL.
- Add TWNU18-to-TWNU19 known-value tests against the canonical contract.
- Integrate schedule quality into the project hub/workbench; standalone quality exists, but project hub quality controls are not yet first-class.
- Expand review workflow schema if required by the SOW: owner, due date, assignment/comment event types, richer statuses, and filters.
- Expand export receipts/report variants; current export supports markdown/html, standard/executive, full/review_items, but no JSON and limited receipt metadata.
- Preserve existing auth posture: do not weaken global auth; keep local mutations operator/admin only.
