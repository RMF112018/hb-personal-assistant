# Phase 10 Prompt 06 — Action Candidate Fixture Runner Proof

**Status:** clean · **proof_passed:** True · **generated_utc:** 2026-06-08T07:07:41.433924+00:00

- repo_sha: `2654ebbd3a9e1d2faf78e6b75ad03585d048834d`
- schema_version: V42
- guard_sum: 0 (must be 0)
- dry_run_receipt_rows: 0 (must be 0)

## Gates

| Gate | Pass |
| --- | --- |
| all_outcomes_matched | True |
| invalid_json_rejected | True |
| missing_required_field_rejected | True |
| stale_forbidden_field_rejected | True |
| no_accept_without_source_refs | True |
| high_risk_routed_to_review | True |
| dry_run_zero_receipts | True |
| receipt_guards_clean | True |
| no_raw_persistence | True |

## Fixture matrix

| Scenario | Expected | Status | Matched | Low conf | High risk | Routing ok |
| --- | --- | --- | --- | --- | --- | --- |
| empty_source_refs | schema_invalid | schema_invalid | True | False | False | True |
| high_risk_preaccepted | schema_invalid | schema_invalid | True | False | False | True |
| high_risk_review | valid | ok | True | False | True | True |
| low_confidence | valid | ok | True | True | False | True |
| malformed_json | schema_invalid | schema_invalid | True | False | False | True |
| missing_required_field | schema_invalid | schema_invalid | True | False | False | True |
| stale_forbidden_field | schema_invalid | schema_invalid | True | False | False | True |
| unavailable_backend | unavailable | unavailable | True | False | False | True |
| valid | valid | ok | True | False | False | True |

## Guardrails

Local-only batch harness; advisory and dry-run (no DB write, no writeback); structured output validated against ActionCandidate before any (here: zero) write; only SHA-256[:12] hashes are surfaced (no raw prompt/response/body/URL/token/path); high-stakes items stay review-only; the 13 no-raw/no-writeback guard columns sum to 0; suite fixtures live in a subdirectory so the ai_jobs glob never sees the intentionally-invalid fixtures.
