# Prompt 07 — Feedback Read Model

## Objective

Create a raw-safe feedback read model for future extractor/ranking improvement.

## Inputs

- accepted candidates
- rejected candidates
- rejection reason codes
- snooze patterns
- duplicate groups
- manual project reassignment, if implemented
- confidence thresholds
- source family performance
- false-positive suppression
- stale/ignored candidates
- lifecycle transition counts

## Output contract

See `references/feedback_read_model_contract.md`.

Expected payload:

- counts by source family
- counts by candidate family
- acceptance rate by family/source
- rejection reason distribution
- snooze distribution and return dates bucketed
- duplicate group counts
- suppression count by reason
- project-review-required count
- source-missing count
- stale/ignored count
- confidence bucket outcomes

## Rules

- Raw-safe counts, hashes, bounded redacted labels only.
- No cloud LLM.
- No raw prompt/response storage.
- Do not materialize summary unless required; prefer a read-only query over events/status tables.

## Tests

Create `tests/test_phase_10_candidate_lifecycle_feedback.py`.

Assertions:

- deterministic summary
- accepted/rejected/snoozed/suppressed/merged counts correct
- confidence buckets stable
- raw forbidden keys absent

