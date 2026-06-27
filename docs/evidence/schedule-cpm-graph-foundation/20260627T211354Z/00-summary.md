# Schedule CPM Graph Diagnostics Foundation — Phase 1

Generated: 20260627T211354Z (UTC)
Branch: feat/schedule-cpm-graph-foundation (off origin/main @ d19e6134)

## What shipped
A graph-diagnostics-only CPM foundation. It builds a directed activity graph from committed
schedule activities and relationships for one `schedule_version_key`, reports structural
diagnostics, and produces a deterministic topological order for acyclic graphs — persisted in
two additive tables. **No CPM dates, float, early/late dates, critical path, or longest path
are computed. No forward/backward pass. No frontend change.**

## Files added
- `src/hb_assistant/construction/analytics/schedule_cpm_graph.py` — typed models
  (ActivityNode, RelationshipEdge, GraphDiagnostic, GraphBuildResult) + `build_graph()`
  (validations + Kahn topological order, deterministic).
- `src/hb_assistant/construction/analytics/schedule_cpm_service.py` — `ScheduleCpmGraphService`
  loads activities/relationships via the repository, builds the graph, persists run + diagnostics.
- `src/hb_assistant/store/schedule_cpm_tables.py` — V83 additive table DDL.
- `src/hb_assistant/store/schedule_cpm_repository.py` — read/write repository + deterministic run id.
- `tests/test_schedule_cpm_graph.py` — 10 unit + 2 integration tests.

## Files modified
- `src/hb_assistant/store/migrator.py` — `_v83_statements()`, version-guarded apply block,
  `LATEST_SCHEMA_VERSION` 82 → 83.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — table_count 471 → 473
  + two `schedule_cpm_*` entries (family `schedule_cpm_v83`, operational_empty_expected).
- 23 test files — table-count assertion 471 → 473 (lockstep); function renamed
  `test_lifecycle_contract_471` → `_473`.
- `scripts/test-schedule.sh` — added `tests/test_schedule_cpm_graph.py`.

## Diagnostics produced
missing_predecessor_activity, missing_successor_activity, self_relationship,
duplicate_relationship, unsupported_relationship_type, open_start, open_finish, cycle.

## Validation
- New tests: 12 passed.
- Full schedule bundle (`scripts/test-schedule.sh`): 173 passed, 2 deselected.
- All 23 count-assertion / migration test files: passed.
- DCMA critical-path test still returns NOT_MEASURABLE_RECALC (unchanged).
- ruff check (new files): clean. mypy (in-scope new files): clean.
- Fresh migrate → version 83, both tables present, idempotent on re-apply.
