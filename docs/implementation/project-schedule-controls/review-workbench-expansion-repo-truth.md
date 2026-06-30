# Phase 8C Review Workbench Expansion Repo Truth

## 1. Current Branch, HEAD, and Working-Tree Status

- Branch: detached HEAD
- HEAD: `a5fa95e374ec1757d144763d0c6af80bc4c96490`
- Prior phases complete through Phase 8B (UDF normalization, readiness-aware metric payloads)

## 2. Existing Review Workbench Infrastructure

| Area | Path |
|------|------|
| Tables V91/V92 | `src/hb_assistant/store/project_schedule_hub_tables.py` |
| Repository | `src/hb_assistant/store/project_schedule_hub_repository.py` |
| Review service | `src/hb_assistant/construction/analytics/project_schedule_review_service.py` |
| Summary orchestration | `src/hb_assistant/construction/analytics/project_schedule_summary_service.py` |
| UDF metrics (8B) | `src/hb_assistant/construction/analytics/project_schedule_udf_normalization_service.py` |
| API routes | `src/hb_assistant/construction/analytics/api.py` |
| Frontend workbench | `frontend/src/pages/ProjectScheduleWorkbenchPage.tsx` |
| Tests | `tests/test_project_schedule_review_workbench.py` |

## 3. `project_schedule_review_items` Schema (V91)

| Column | Purpose |
|--------|---------|
| `review_item_id` | Primary key |
| `project_key`, `schedule_version_key` | Scope |
| `stable_item_key` | Dedupe key (unique per version) |
| `item_type`, `item_title`, `priority` | Display/triage |
| `review_status` | `open`, `watching`, `reviewed`, `dismissed` |
| `pm_notes` | Operator notes |
| `evidence_json` | Extended cue metadata (Phase 8C) |
| `source_activity_id` | Activity link |
| `reviewed_by_operator`, `reviewed_at` | Disposition audit |

## 4. `project_schedule_review_item_events` Schema (V92)

Event types: `created`, `synced`, `status_changed`, `notes_changed`, `carried_forward`

## 5. Current API Behavior

| Route | Role | Behavior |
|-------|------|----------|
| GET `/schedule/review-items` | viewer+ | Preview merge via `build_review_items` |
| POST `/schedule/review-items` | operator | `sync_review_workbench` materializes candidates |
| PATCH `/schedule/review-items/{id}` | operator | Status/notes update |

Phase 8C adds: GET detail, GET events, extended query filters.

## 6. Current Candidate Sources (pre-8C)

`ProjectScheduleReviewService._collect_candidates`: drivers, milestones, negative float, worsened float, critical remaining.

## 7. Phase 8B Metric Payloads (cue sources)

| Metric | 8B state | 8C materialization |
|--------|----------|-------------------|
| `should_have_finished_status` | Activity categories when available | Activity-level cues |
| `window_start_accuracy` | Window counts when available | Late/did-not-start activity cues |
| `window_finish_accuracy` | Window counts when available | Late/did-not-finish activity cues |
| `critical_issues_category_model` | Category counts | Category cues when count > 0 |
| `delay_analysis` | Period movement when diff exists | Period review cue (caveated) |
| `schedule_quality_findings` | Count in critical issues | Per-finding activity cues |
| Compression readiness | 8A baseline service | Readiness/blocker cue |

## 8. Cue Confidence Classification

| Confidence | Meaning |
|------------|---------|
| `production_backed` | Deterministic signal with schedule + join proof |
| `partial_dimension_support` | Core signal available; UDF dimensions sparse |
| `sparse_support` | Signal exists but dimension coverage low |
| `readiness_only` | Preview only; not materialized |
| `blocked` | Metric unavailable; not materialized |

## 9. Migration Required?

**No.** Extended cue fields stored in `evidence_json`.

## 10. Explicit Non-Scope

- No claims analysis, causation, responsibility, entitlement, compensability
- No external reports or email
- No import pipeline changes
- No Phase 8A baseline semantic changes
- No Phase 8B UDF normalization semantic changes
