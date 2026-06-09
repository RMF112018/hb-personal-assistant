# Validation Matrix — Follow-up Watch Quality (Prompt 03)

| Area | Command / Method | Expected | Actual | Status |
|---|---|---|---|---|
| Compile | `compileall follow_up_watch.py second_brain.py` | pass | COMPILE_OK | ✅ |
| New regression | `pytest tests/test_phase_10_follow_up_watch_report.py` | pass | 3 passed | ✅ |
| Targeted tests | `pytest -k "followup or follow_up or email_followup or waiting or stale"` | pass | 165 passed | ✅ |
| Lint | `ruff check <changed>` | pass | All checks passed | ✅ |
| Types | `mypy follow_up_watch.py` | pass | no issues | ✅ |
| Operator-action buckets | report builder on temp DB | 6 groups populated | one item per group (total 6) | ✅ |
| Stale proof | aged item, no due | watch=stale, aged_no_due | ok=true | ✅ |
| Closed-loop proof | terminal status | watch=closed | ok=true | ✅ |
| Waiting/needs-review | waiting_on_me/others + no-source | grouped + insufficient_evidence | ok=true | ✅ |
| Model-unavailable | deterministic, no model | identical repeat build | identical=true | ✅ |
| Guard columns | scan --apply on temp DB, sum guards | zero | all_guard_columns_zero=true | ✅ |
| Safety scan | forbidden-pattern scan | no findings | TOTAL_FINDINGS=0 | ✅ |
| Production DB checksum | sha256 before/after | unchanged | UNCHANGED=True | ✅ |
| DB migration | N/A | — | no schema change | ✅ N/A |

Notes: report is read-only/deterministic (no model, no clock read in scoring). Quality gates:
no source ref → insufficient_evidence → needs_review (non-actionable); terminal status + active
waiting + no completion → contradictory → needs_review. Stale threshold is the explicit, configurable
`--stale-after-days` (default 14). The watch report complements the brief's V45 pending section
without duplication (see `07-daily-brief-consumption-proof.md`).
