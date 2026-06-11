# Validation Matrix

| Validation item | Command / test | Expected result | Evidence file | Merge-blocking threshold | Raw-safety notes |
|---|---|---|---|---|---|
| Repo state | `git fetch origin && git status --short && git log --oneline --decorate -30` | Branch, HEAD, main, origin/main, dirty tree documented | `00_repo_truth.md` | Unknown branch/dirty owned files not explained | No raw output |
| Schema audit | safe sqlite PRAGMA/table count checks on `/tmp` copy | Tables/columns confirmed; migration need justified | `01_schema_audit.json` | Production DB mutation or unexplained missing required tables | Counts/column names only |
| Existing review regression | `pytest tests/test_phase_10a_candidate_review.py tests/test_phase_10a_candidate_review_cli.py` | Existing tests pass | `10_db_copy_validation.md` | Any regression | Test output only |
| Read model coverage | `pytest tests/test_phase_10_candidate_lifecycle_read_model.py` | All eligible families appear with raw-safe fields | `02_review_queue_sample.json` | Missing family without documented exclusion | Bounded redacted text only |
| Lifecycle transitions | `pytest tests/test_phase_10_candidate_lifecycle_operations.py` | accept/reject/snooze/close/reopen idempotent | `03_lifecycle_transition_matrix.json` | Duplicate or non-idempotent events | Reason codes, not raw notes |
| Promotion | `pytest tests/test_phase_10_acceptance_promotion.py` plus new promotion tests | accepted rows inserted once; source refs preserved directly or indirectly | `04_promotion_source_ref_proof.json` | Accepted item without source-ref trace | Hash refs only |
| Duplicate/merge | `pytest tests/test_phase_10_candidate_duplicate_merge.py` | duplicate group stable; merge preserves refs; replay no noise | `05_duplicate_merge_idempotency.json` | Duplicate review noise after replay | Group hashes only |
| Feedback | `pytest tests/test_phase_10_candidate_lifecycle_feedback.py` | feedback summary deterministic and raw-safe | `06_feedback_summary.json` | Raw fields or inconsistent counts | Reason codes and counts only |
| Daily brief integration | `pytest tests/test_phase_10_candidate_lifecycle_daily_brief.py` | rejected/suppressed hidden; snoozed returns only when due; accepted/stale visible | `07_daily_brief_lifecycle_output.md` | Misleading success or hidden review-required items | Rendered output scanned |
| Usefulness gate | `pytest tests/test_phase_10_candidate_lifecycle_usefulness_gate.py` | lifecycle contradictions fail/degrade honestly | `08_usefulness_gate_lifecycle.json` | Gate passes contradictions | Metrics only |
| CLI | `pytest tests/test_phase_10_candidate_lifecycle_cli.py` | commands operate on explicit `--db`; local-only JSON | CLI evidence section | CLI defaults to prod writes | No raw keys |
| No raw leak | package scan plus rendered output scan | forbidden sentinels absent | `09_no_raw_leak_scan.json` | Any raw body/URL/token/prompt/response leak | Fail closed |
| DB integrity | `sqlite3 "$COPY_DB" "PRAGMA integrity_check;"` | `ok` | `10_db_copy_validation.md` | Any DB corruption | No row dumps |
| Guard columns | template SQL guard check | guard sum = 0 | `10_db_copy_validation.md` | Any guard > 0 | Guard counts only |
| Idempotency replay | apply same lifecycle operation twice on `/tmp` copy | second run no-op or same deterministic event id | `05_duplicate_merge_idempotency.json` | Duplicate accepted items/events | Counts only |
| Final handoff | `prompts/13_final_handoff.md` | complete handoff using template | `11_final_handoff.md` | Missing safety/validation data | Raw-free |

