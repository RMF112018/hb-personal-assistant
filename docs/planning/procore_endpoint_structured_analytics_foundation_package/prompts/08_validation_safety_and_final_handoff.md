# 08 — Validation, Safety, and Final Handoff

## Objective

Run full validation, prove safety constraints, commit the implementation branch, and prepare the final handoff.

## Required validation suite

Run targeted tests plus broad checks appropriate to repo conventions. At minimum:

```bash
python -m pytest tests -q
python -m ruff check src tests
python -m mypy src
```

If broad checks expose unrelated pre-existing failures, isolate and document them, then run targeted package tests to prove package-owned files pass.

## Required DB validation

Fresh DB migration test, copied production DB migration test, rollback/reversibility notes, production DB unchanged proof, raw landing table migration proof, structured table migration proof, and source-ref/idempotency proof.

## Required safety scans

Prove no raw payloads or secrets are emitted to evidence files, daily brief output, polished browser output, Obsidian output, status JSON, CLI outputs, or tests/snapshots.

Search for likely forbidden patterns: bearer tokens, signed URL query params, `access_token`, `refresh_token`, `client_secret`, raw Procore API URLs with private query strings, raw HTML bodies, and emails/phone patterns where not expected.

## Required final handoff

Use `templates/final_handoff_template.md`. Include branch and commit SHA, files changed, migrations added, structured endpoint tables added/reconciled, endpoint coverage table, raw landing coverage, backfill/reprocessing instructions, analytics query examples, daily brief downstream changes, validation commands/results, no-writeback proof, production DB unchanged proof, known limitations, and recommended next step.

## Commit

Commit only after validation and evidence are complete. Do not merge to main.
