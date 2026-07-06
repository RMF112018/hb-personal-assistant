# 05 — Rule-Based Extraction Proof

Deterministic, LLM-free extraction. Source: `tests/test_claim_extraction.py` (16 tests, all pass).

## Types extracted (no Qwen/Ollama)
`extract_claims_from_text` (`claim_extraction.py`, `EXTRACTOR_VERSION="rule_based-v1"`) maps text to
claim types via bounded regex/keyword rules. Proven per the spec examples
(`test_single_rule_maps`, `test_each_claim_type_extracted`):

| text | claim_type |
|---|---|
| "we decided to keep MCP read-only" | decision_candidate |
| "risk: switchgear delivery may slip" | risk |
| "warranty expires March 4, 2027" | date |
| "I prefer 65 percent hydration" | preference |
| "assumption: NAS remains canonical host" | assumption |
| "I will send the revised schedule" | commitment |
| "due by Friday" | task_candidate |

## Properties
- `test_extraction_is_deterministic` — same input → identical `(type, text)` sequence (order-stable).
- `test_evidence_excerpts_bounded` — each candidate's evidence ≤ 400-char segment cap (the repo bounds
  further to `EVIDENCE_MAX_CHARS`=2000). No unbounded blobs.
- Pure: no DB, no I/O — extraction never writes; ingestion is a separate validated step.

## Ingestion seam
`ingest_claim_candidates(repo, source_id, candidates, extractor="manual|rule_based|future_qwen")` —
`test_ingest_seam_is_internal_and_validated`: enforces provenance (unsupported → raise), writes only
claim tables, and is an internal function (no remote claim-write tool exposes it). Reserved
`future_qwen` lets a later model path reuse this exact validated seam with no schema change.
