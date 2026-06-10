# Validation Matrix — Candidate Review UX (Prompt 02)

| Area | Command / Method | Expected | Actual | Status |
|---|---|---|---|---|
| Compile | `compileall candidate_review.py second_brain.py` | pass | COMPILE_OK | ✅ |
| New regression | `pytest tests/test_phase_10_candidate_review_report.py` | pass | 3 passed | ✅ |
| Targeted tests | `pytest -k "candidate or review or apply or daily_brief_action or followup"` | pass (modulo pre-existing) | all pass except 1 pre-existing | ✅ |
| Lint | `ruff check <changed>` | pass | All checks passed | ✅ |
| Types | `mypy candidate_review.py` | pass | no issues | ✅ |
| Final output (report) | evidence generator | legible Markdown + JSON | `01-review-list-final-output.md` | ✅ |
| Detail / export / preview | evidence generator | artifacts present | `02`/`03`/`04` | ✅ |
| Apply cap | batch accept `--apply --max-actions 2` over 5 | 2 applied, 3 over cap | applied=2, skipped_over_cap=3, accepted_rows=2 | ✅ |
| Accept/reject | service transitions + audit events | status flips + event ids | accept→accepted, reject→rejected, events written | ✅ |
| Safety scan | forbidden-pattern scan | no findings | TOTAL_FINDINGS=0 | ✅ |
| Production DB checksum | sha256 before/after | unchanged | UNCHANGED=True | ✅ |
| DB migration | N/A | — | no schema change | ✅ N/A |

## Pre-existing failure (not this candidate)

`tests/test_phase_09_review_burden_cli.py::test_review_burden_and_queue_and_clusters_smoke` fails with
`OperationalError('unable to open database file')`. Confirmed pre-existing: it fails identically with
this candidate's changes stashed (it invokes `review burden` against the real app DB, which is not
openable in this environment). It exercises `burden`/`queue`/`clusters` — code this candidate did not
touch. Recorded, not fixed (per the global validation policy + `hb-preexisting-test-failures`).

## Notes

- All review operations ran on disposable temp DBs; production (`PathPolicy.get_db_path()`) read once,
  never written. See `08-production-db-unchanged-proof.txt`.
- The report is read-only / dry-run; it persists nothing. The bounded apply remains the existing
  `review accept … --apply --max-actions`.
