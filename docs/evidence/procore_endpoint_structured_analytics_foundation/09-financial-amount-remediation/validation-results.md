# Validation results

Interpreter: `.venv/bin/python3.12` (the real toolchain; bare `python` is an empty 3.14),
`PYTHONPATH` pinned to this worktree's `src` (the editable `.pth` points at the main-repo `src`,
which lacks `structured_analytics`).

## Targeted (package-owned)

```
python -m pytest tests/test_procore_structured_analytics_foundation.py -q   -> 18 passed
python -m ruff check src/hb_assistant/procore src/hb_assistant/cli/procore.py \
                     tests/test_procore_structured_analytics_foundation.py    -> All checks passed!
```
18 = 8 pre-existing + 10 new financial-extraction tests (precedence, nested summary path,
schedule_impact exclusion, generic-fallback regression guard, end-to-end backfill for
invoice items / invoices / change orders, idempotency, no-live posture, coverage diagnostic).

## Branch-owned

```
git diff --name-only origin/main...HEAD -- 'tests/**' | xargs python -m pytest -q  -> 132 passed
```

## Broad

```
python -m pytest tests -q          -> 22 failed (pre-existing baseline; see below), package suite green
python -m ruff check src tests     -> 7 errors, all in non-branch files
python -m mypy src                 -> 2 errors in review_burden_mart.py (non-branch file)
```

### Baseline / unrelated classification

All 22 broad pytest failures are in files **not in the branch diff** (`origin/main...HEAD`) and
**none import `structured_analytics`**:

```
test_automation_executor_service.py     test_phase_08b_gate_coverage.py
test_calendar_event_indexing.py         test_phase_08c_financial_completeness.py
test_email_body_indexing.py             test_phase_09_review_burden_cli.py
test_email_body_security.py             test_phase_10_email_task_extraction.py
test_phase_08b_data_quality_gates.py    test_procore_live_inspect.py
test_repo_sensitive_scan.py             test_retrieval.py
test_second_brain_no_writeback_proof.py
```

These are pre-existing repo/environment baseline failures (e.g. retrieval embedder/model-dependent;
and the "clean repo" proofs `test_second_brain_no_writeback_proof` / `test_repo_sensitive_scan` trip
on the worktree's pre-existing foreign uncommitted evidence edits, which this remediation neither
created nor touched). Per the package guardrails, unrelated baseline failures are documented, not
fixed.

The broad ruff (7) and mypy (2) errors are likewise all in files outside this change
(`wrappers.py`, `review_burden_mart.py`, and several non-branch test files); the
diff-intersection with the two files this remediation edits is empty.

## DB-copy acceptance

See `before-after-amount-coverage.md` and `db-copy-backfill-proof.md`: every financial table moved
0% → 100% amount coverage, **zero blockers**, prod sha256 before==after, schema head 46 (unchanged),
backfill idempotent (30,059/30,059, 0 live calls, 0 writeback).
