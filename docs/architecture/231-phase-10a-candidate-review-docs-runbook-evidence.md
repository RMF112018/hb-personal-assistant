# 231. Phase 10A — Candidate Review CLI docs, runbook, and evidence (closeout)

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

The Candidate Review CLI is fully implemented, tested, and proofed (records
223–230, v1.3.0–v1.10.0). This record is the documentation closeout: it documents
the operator-facing surface, preserves captured validation evidence, and records the
command-path reconciliation.

## Decision

- **Operator runbook** —
  `docs/runbooks/phase-10a-candidate-review-cli-runbook.md` (new): posture, the
  command-path reconciliation table, each verb with an example invocation, the
  batch dry-run/`--apply` workflow, the exit-code map, and the guardrail
  re-statement. Matches the `phase-08d-*-runbook.md` format.
- **Captured evidence** —
  `docs/evidence/construction-intelligence-phase-10a-candidate-review-cli/02-cli-review-evidence.md`
  (new): real captured `review --help`; `summary`/`list`/`show` JSON; accept/ignore
  (→suppressed)/reject JSON; the guardrail SQL attestation (13 `_P10_GUARDS` sum = 0
  across all four candidate-review tables after actions); and the package validation
  result (66 passed). Captured against a throwaway local `--db`, then deleted.
- **Command-path reconciliation** (the prompt's documentation note): batch
  extraction is `second-brain extract-packets`; candidate review is
  `second-brain review …`; the earlier Phase 10 raw-content commands remain under
  `second-brain phase-10 …`. Recorded in the runbook (table) and the README entry.
- **README ledger** — added a focused **Phase 10A (Candidate Review CLI) —
  Closed/Delivered** entry to the Repository Status block (Prompts 00–09 /
  v1.3.0–v1.10.0), citing the evidence bundle, architecture 223–231, and the
  command-path clarification. Scoped to this package; prior Phase 10 raw-content
  history was not retroactively authored (noted that those records exist).
- **Architecture index** — backfilled `docs/architecture/00-README.md` with
  one-line pointers for records 223–231 (they were created without being indexed).

## Verified

The package validation command —
`pytest tests/test_phase_08d_no_raw_access.py tests/test_phase_08d_no_writeback.py
tests/test_second_brain_no_writeback_proof.py tests/test_phase_10a_candidate_review.py
tests/test_phase_10a_candidate_review_cli.py` — **66 passed** (captured into the
evidence doc). All CLI samples were captured from live invocations. The new docs
were grepped clean of raw markers (URL / PEM-header / credential-token patterns).

## Guardrails / non-goals

Docs only — no production code/test/migration change. No retroactive Phase 10
raw-content ledger history beyond the command-path note. No raw content in any doc
(CLI output is redacted; evidence captured via a throwaway local DB, then deleted).
No email/calendar/Graph/Procore/external writeback.
