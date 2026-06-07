# Phase 10 Prompt 04 — Local Model Structured Output Client Proof

**Status:** clean · **proof_passed:** True · **generated_utc:** 2026-06-07T21:33:43.682776+00:00

- repo_sha: `f294eeac82d481fcf0a53f4f66dd4a2eff7bf3db`
- schema_version: V42
- guard_sum: 0 (must be 0)

## Gates

| Gate | Pass |
| --- | --- |
| fixtures_schema_valid | True |
| heavy_profile_blocked | True |
| unavailable_fallback_redacted | True |
| dry_run_zero_writes | True |
| apply_single_receipt | True |
| receipt_guards_clean | True |
| receipt_hash_only | True |

## Fixtures validated

| Fixture | Schema valid | input_context_hash | output_hash |
| --- | --- | --- | --- |
| tests/fixtures/local_ai/email_task_candidate_001.json | True | 1047d6e40aa7 | 9fc885ddbd04 |
| tests/fixtures/local_ai/commitment_candidate_001.json | True | 1de5efd3d99a | bb7de0164864 |
| tests/fixtures/local_ai/follow_up_monitor_001.json | True | 44136fa355b3 | 4e7e82574fae |
| tests/fixtures/local_ai/relationship_candidate_001.json | True | 44136fa355b3 | 5462543549d9 |

## Receipt sample (hash-only)

```json
{
  "model_run_receipt_id": "1a0fd3a225e644c8b834966ea3aea5ed",
  "profile_id": "default_extract",
  "provider": "ollama",
  "model_name": "qwen3:14b",
  "task_type": "extract_email_tasks",
  "status": "ok",
  "input_context_hash": "0230c6b1d833",
  "output_hash": "9fc885ddbd04",
  "schema_name": "ActionCandidate",
  "schema_valid": true,
  "input_token_count": null,
  "output_token_count": null,
  "latency_ms": 0,
  "fallback_used": false,
  "created_utc": "2026-06-07T21:33:43.677034+00:00"
}
```

## Guardrails

Local-only; schema-validated before any write; receipts carry only SHA-256[:12] hashes and metadata (no raw prompt/response/body/URL/token/path); 13 no-raw/no-writeback guard columns sum to 0; heavy profiles blocked unless explicitly enabled; dry-run is the default; backend and validation errors are redacted to category codes.
