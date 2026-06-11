# Prompt 12 — Validation and Evidence

## Objective

Run full validation on repo code and `/tmp` DB copies. Produce raw-free evidence.

## Static/tests

```bash
python -m compileall src tests
ruff check src tests
pytest tests/test_phase_10a_candidate_review.py tests/test_phase_10a_candidate_review_cli.py
pytest tests/test_phase_10_acceptance_promotion.py tests/test_phase_10_follow_up_monitor.py tests/test_phase_10_daily_brief_synthesis.py tests/test_phase_10_usefulness_gate.py
pytest tests/test_phase_10_candidate_lifecycle_read_model.py
pytest tests/test_phase_10_candidate_lifecycle_operations.py
pytest tests/test_phase_10_candidate_duplicate_merge.py
pytest tests/test_phase_10_candidate_lifecycle_feedback.py
pytest tests/test_phase_10_candidate_lifecycle_daily_brief.py
pytest tests/test_phase_10_candidate_lifecycle_usefulness_gate.py
pytest tests/test_phase_10_candidate_lifecycle_cli.py
pytest tests/test_phase_10_candidate_lifecycle_no_raw_leak.py
```

If strict mypy scopes exist for modified modules, run the applicable scoped mypy command and document it.

## DB validation

Use `templates/db_copy_validation_commands.md`.

Required proof:

- DB copy integrity
- migration result if applicable
- review queue count
- lifecycle transition count
- accepted task/commitment count
- source-ref coverage
- project-key/review-required coverage
- duplicate replay/idempotency
- reject/suppress hidden from normal daily brief
- snooze return behavior
- usefulness gate lifecycle contradictions
- no raw leak scan
- production DB SHA unchanged before/after validation

## Evidence

Write evidence files under:

`docs/evidence/phase-10-candidate-lifecycle-review-queue/`

Do not include raw content.

