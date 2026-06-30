# Phase 1 Audit Findings — Fresh Agent

**UTC:** 2026-06-30T13:08:46Z  
**Worktree:** `feature/schedule-canonical-package-merge-20260630T093009Z`  
**Base HEAD:** `e5187c85`  
**Auditor:** fresh-agent (independent verification of prior uncommitted work)

## Summary verdict

| Area | Verdict |
|------|---------|
| Canonical XER/XML merge | **PASS** (pending test/proof re-run) |
| Baseline separation | **PASS** |
| Uniqueness without `import_id` | **PASS** |
| Lineage/conflicts | **PASS** |
| Idempotent re-import | **PASS** (logic + test present) |
| CPM test edits | **PASS** (isolation-only) |
| Proof script isolation | **PASS** |
| Proof script count provenance | **PARTIAL** — uses correct SQL internally; JSON lacks explicit `count_sources` labels (amendment #6: extend before commit) |
| Schema/migration | **PASS** — no new migration required |

**Blockers before commit:** add explicit `count_sources` to proof script output; independent test/proof re-run must pass.

---

## 17 required audit questions

### 1. Does `schedule_package_assembly.py` merge equivalent XER/XML current schedules into one canonical model?

**PASS.** `_merge_current_bundle` replaces simple `_merge_rows` with `_merge_activity_rows`, `_merge_relationship_rows`, `_merge_canonical_collection`. Assembly mode `unified_companion_package` when companions exist.

### 2. Does it use XER `TASK.task_code` and XML `Activity.Id` as canonical activity key?

**PASS.** `_canonical_activity_id` normalizes `activity_id` from parsed rows. XML parser maps `Id`/`ActivityId` to `activity_id` (`schedule_xml_parser.py`).

### 3. Does it preserve XER `TASK.task_id` and XML `Activity.ObjectId` as source object IDs?

**PASS.** `_merge_activity_into` records `source_activity_object_id` in `source_object_ids_json`.

### 4. Does it scope XML `<Project>` as current schedule data?

**PASS.** Only `role="current"` entities enter `_merge_current_bundle`. XML parser assigns `role="current"` to Project children.

### 5. Does it keep XML `<BaselineProject>` separate from current records?

**PASS.** `baseline_entities` handled in `_lineage_rows` as `baseline_evidence`; not merged into `merged_current_bundle.activities`.

### 6. Does it deduplicate relationships by schedule-scoped identity?

**PASS.** `_relationship_key(pred, succ, normalized_type, lag_value)`; `_merge_relationship_rows` dedupes by key.

### 7. Does it deduplicate activity codes by schedule-scoped identity?

**PASS.** `_merge_canonical_collection` keys `("activity_id", "code_type", "code_value")`.

### 8. Does it deduplicate UDF values by schedule-scoped identity?

**PASS.** Keys `("activity_id", "udf_type_name", "udf_value")`. Column name `udf_type_name` matches repo schema (spec `udf_name_or_id` = same field).

### 9. Does it persist/expose field lineage for merged activity fields?

**PASS.** `field_lineage_json` written per field in `_merge_activity_into`; persisted via `raw_source_fields_json` in commit; `get_activity_merge_lineage()` exposes it.

### 10. Does it persist/expose conflicts for conflicting non-empty values?

**PASS.** `field_conflicts_json` + synthetic test `test_canonical_activity_merge_records_inspectable_field_conflict`.

### 11. Does it avoid `import_id` in canonical uniqueness keys?

**PASS.** See dedicated section below.

### 12. Does re-importing the same ZIP avoid duplicate current records?

**PASS.** `idempotent_reimport` in `schedule_import_service.py`; test asserts `committed_imports == 1` and zero duplicate buckets.

### 13. Does the proof script use an isolated non-production DB?

**PASS.** `tempfile.TemporaryDirectory` + `SQLiteMigrator` on temp path.

### 14. Do test changes weaken or skip existing CPM tests?

**PASS.** No tests skipped; no algorithm assertions removed except `len(runs)==1` replaced with targeted lookup (see CPM section).

### 15. Are CPM test changes merely matching implementation vs preserving behavior?

**PASS (isolation adaptation).** Changes add `clear_schedule_cpm_runs()` because import commit now auto-triggers CPM graph. Stage-chain assertions unchanged.

### 16. Schema assumptions — migration needed?

**PASS.** Uses existing `procore_ep_schedule_*`, `schedule_baseline_projects`, `raw_source_fields_json`. No migration in diff.

### 17. Does Phase 1 preserve existing CPM recompute behavior?

**PASS.** Import commit still triggers CPM; `computed_activity_count` returned; proof records CPM status. No CPM algorithm changes in Phase 1 diff.

---

## `import_id` exclusion proof

Searched merge helpers, persist paths, tests, and proof script duplicate-bucket queries.

| Location | Uniqueness key / GROUP BY | Includes `import_id`? |
|----------|---------------------------|----------------------|
| `_canonical_activity_id` | `activity_id` (normalized) | **No** |
| `_relationship_key` | pred, succ, type, lag_value | **No** |
| `_merge_canonical_collection` codes | activity_id, code_type, code_value | **No** |
| `_merge_canonical_collection` udfs | activity_id, udf_type_name, udf_value | **No** |
| `test_schedule_import_health_foundation` duplicate SQL | schedule_version_key + entity keys | **No** |
| `prove_schedule_canonical_package_merge._duplicate_buckets` | schedule_version_key + entity keys | **No** |
| Activity/rel rows at persist | `import_id` stored as lineage column on rows | **Lineage only** — not in dedup GROUP BY |

`import_id` appears in commit payloads, supersede tracking, and row lineage — **not** in canonical uniqueness keys.

---

## CPM test non-weakening proof

| File | Change | Algorithm assertions | Verdict |
|------|--------|---------------------|---------|
| `test_schedule_cpm_backward_pass.py` | `clear_schedule_cpm_runs` after import | Unchanged | Isolation-only |
| `test_schedule_cpm_criticality.py` | same | Unchanged | Isolation-only |
| `test_schedule_cpm_float.py` | same | Unchanged | Isolation-only |
| `test_schedule_cpm_graph.py` | `len(runs)==1` → `next(... cpm_run_id ...)` + `clear_schedule_cpm_runs` in rerun test | `node_count`, `edge_count`, `is_acyclic`, `topological_order`, diagnostics preserved | Isolation-only |
| `test_schedule_cpm_longest_path.py` | `clear_schedule_cpm_runs` | Unchanged | Isolation-only |
| `test_schedule_health_cpm_aggregation.py` | `clear_schedule_cpm_runs` | Unchanged | Isolation-only |

No float/criticality/path/graph correctness assertions removed.

---

## Defects / actions

| ID | Severity | Item | Action |
|----|----------|------|--------|
| D1 | Low | Proof JSON lacks explicit `count_sources` | Add to `scripts/prove_schedule_canonical_package_merge.py` before commit — **blocked: agent mode required** |
| D2 | Info | `phase1-summary.md` stale test-schedule failure claim | **RESOLVED** — fresh run: 323 passed |
| D3 | — | All gates | **PASS** — see validation section below |

## Fresh-agent validation results (2026-06-30T13:22Z)

| Command | Result |
|---------|--------|
| Focused pytest (43 tests) | PASS |
| `pytest -k "schedule and import"` | PASS (1 skip) |
| `.venv/bin/python -m py_compile` | PASS |
| Proof script TWNU18/19 | PASS — exact acceptance counts |
| `scripts/test-schedule.sh` | PASS — 323 passed, 2 deselected |

Evidence: `pytest-*-before-fixes.txt`, `prove-schedule-canonical-package-merge.txt`, `scripts-test-schedule-before-fixes.txt`

---

## Files in scope (preaudit)

- `schedule_package_assembly.py` (+278)
- `schedule_import_service.py` (+31)
- `schedule_activity_repository.py` (+42)
- `tests/test_schedule_import_health_foundation.py` (+269)
- 6 CPM test files (+6 each isolation)
- `tests/schedule_project_test_helpers.py` (+clear_schedule_cpm_runs)
- `scripts/prove_schedule_canonical_package_merge.py` (untracked)
