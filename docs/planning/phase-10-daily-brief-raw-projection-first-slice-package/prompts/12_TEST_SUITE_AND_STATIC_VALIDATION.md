# 12 — Test Suite and Static Validation

## Objective

Add targeted tests that prove the first-slice behavior and safety gates.

## Required test coverage

Add or update tests for:

1. V49 projection activation wrapper/stage.
2. Daily-run stage ordering and receipts.
3. Calendar candidate persistence + source refs.
4. Calendar project resolution / needs-review behavior.
5. Procore ranking/suppression + source refs.
6. Candidate source-ref coverage gate.
7. Usefulness/contradiction known-bad cases.
8. Email/follow-up data-gap honesty.
9. Guard columns remain zero on structured/receipt tables.
10. No raw fields in status/evidence receipts.

## Suggested commands

Run the most targeted tests first, then broader scoped checks:

```bash
python -m pytest tests/test_email_calendar_structured_projection_remediation.py tests/test_email_calendar_consumer_read_models.py tests/test_phase_10_daily_brief_candidate_projection.py tests/test_phase_10_daily_brief_source_ref_gate.py tests/test_phase_10_usefulness_gate.py -q
python -m compileall src/hb_assistant
python -m ruff check src tests
python -m mypy src/hb_assistant || true
```

If full mypy is not repo-clean, document scoped type-check results and existing unrelated failures separately.

## Evidence

Create:

- `24-validation-results.md`

## Acceptance

- New/changed tests pass.
- Static checks are clean or unrelated existing failures are documented with evidence.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
