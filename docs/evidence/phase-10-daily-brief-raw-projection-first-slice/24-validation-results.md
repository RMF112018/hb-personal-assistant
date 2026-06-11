# 24 — Validation Results

## Tests

Targeted first-slice + affected suites (run with `.venv/bin/python3.12 -m pytest -p no:cacheprovider`):

| Suite | Result |
|---|---|
| `test_phase_10_first_slice_projection_activation.py` (NEW, 15 tests) | ✅ pass |
| `test_phase_10_pipeline.py` | ✅ pass |
| `test_phase_10_daily_run.py` | ✅ pass |
| `test_phase_10_usefulness_gate.py` | ✅ pass |
| `test_phase_10_calendar_meeting_prep.py` | ✅ pass |
| `test_phase_10_procore_digest.py` | ✅ pass |
| `test_phase_10_procore_ranking.py` | ✅ pass |
| `test_phase_10_daily_brief_source_ref_gate.py` | ✅ pass |
| `test_email_calendar_structured_projection_remediation.py` | ✅ pass |
| `test_email_calendar_consumer_read_models.py` | ✅ pass |
| `test_email_calendar_full_raw_content_ingestion.py` | ✅ pass |
| `test_email_calendar_projection_completeness.py` | ✅ pass |
| `test_daily_brief_context.py` | ✅ pass |

New first-slice coverage:
- projection_activation: dry-run writes nothing; apply writes structured rows + receipts; no-raw DB is honest `no_raw_rows`; unmapped family degrades/fails without partial; receipts emit no raw values.
- pipeline: projection stage runs first and does not consume the candidate persist budget.
- email/follow-up data-gap classifier: data_gap / populated / not_configured.
- calendar prefers the V49 structured substrate (raw-landing fallback).
- usefulness gate contradiction checks (a)-(d) fire on known-bad; backward-compatible without `stage_context`.

## Static checks

| Check | Scope | Result |
|---|---|---|
| `ruff check` | all changed src + new test | ✅ All checks passed |
| `ruff format --check` | new module `projection_activation.py` | ✅ clean (edited legacy modules are outside the strict format scope — their base versions are not ruff-formatted either, so they were left unchurned) |
| `mypy` | `projection_activation.py`, `email_followup_readiness.py`, `pipeline.py`, `usefulness_gate.py`, `daily_run.py`, `calendar_prep.py`, `repositories.py` | ✅ Success: no issues found |
| `compileall` | all changed modules | ✅ OK |

## Pre-existing unrelated failures (NOT caused by this slice)

- `test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table` — fails on a clean tree (verified by stashing this slice's `src/` edits: the test fails identically, `assert 0 == 1`). It is a local-model-dependent extraction test (no local model returns a commitment in this environment), in a module this slice does not touch.
