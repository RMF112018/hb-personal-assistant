# Bug / gap log

ID: P1-PURGE-REMAINING-COUNT
Stage: Gate 0.6
Area: schedule_clean_db purge
Symptom: `remaining_tropical_schedule_records` reported 931097 after apply; diff/baseline orphan rows remained
Expected: Tropical schedule-domain rows zeroed per gate metric
Actual: Core import tables zeroed (identities/imports/CPM=0) but diff detail facts and global baseline cache rows remained until supplemental SQL on copied DB
Evidence: 11-tropical-purge-apply.json, 14-clean-db-zero-record-verdict.md
Severity: P1
Blocks production use: no (workaround on copied DB)
Blocks full validation: no (with supplemental cleanup documented)
Recommended fix: Extend purge planner to delete schedule_version_diff_* and baseline rows keyed to purged imports

ID: P2-COMMIT-PROJECT-KEY
Stage: 4
Area: import API
Symptom: First import commit returned 422 missing project_key
Expected: Project-scoped commit accepts import_id alone or documents required body fields
Actual: Required `project_key` in JSON body for `/api/projects/tropical/schedule/import-commit`
Evidence: 27-stage04-import-commit-response.json (first failed attempt)
Severity: P2
Blocks production use: no
Blocks full validation: no
Recommended fix: Document in operator runbook; optional OpenAPI alignment

ID: P3-PHASE0-READINESS-EVIDENCE
Stage: Gate 0.2
Area: readiness script
Symptom: `ready_for_full_clean_db_validation: false` due to missing `27-phase0-summary.md` in evidence dir
Expected: Readiness independent of prior evidence dir contents
Actual: False negative on fresh validation evidence dir
Evidence: 05-phase0-readiness-check.json
Severity: P3
Blocks production use: no
Blocks full validation: no
Recommended fix: Scope readiness check to tooling not prior evidence filenames
