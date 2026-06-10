Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 06 — Email Raw Enrichment Eligibility and Readiness

## Objective

Make the V45 email follow-up raw enrichment path production-legible by adding a readiness/eligibility surface that explains no-op conditions and proves what can safely enrich.

## Required implementation

Add a read-only eligibility builder and CLI surface, suggested command:

```bash
hb-assistant second-brain follow-up-watch enrich-readiness --json
```

Accept equivalent naming if it fits existing CLI patterns.

The report must include:

- accepted task count
- accepted commitment count
- accepted total
- accepted with candidate ID
- accepted with source refs
- accepted with email source refs
- accepted with raw email content available
- eligible for raw enrichment
- already enriched pending count
- already enriched accepted/rejected/superseded count
- skipped counts by reason:
  - no_candidate_id
  - no_candidate_source_refs
  - no_email_source_ref
  - no_raw_email_content
  - already_pending
  - already_final_review_status
  - local_model_unavailable
  - raw_policy_disabled
  - source_link_invalid
  - unsupported_candidate_type
- sample safe candidate IDs, bounded
- guardrails

## Critical safety

Readiness must not load or print raw email content. It may check existence by hash/source ref only.

## Evidence

Create:

- `11-email-raw-enrichment-eligibility-proof.json`

## Tests

Add tests for:

- no accepted items
- accepted but no source refs
- accepted with non-email refs
- accepted with email refs but no raw content
- eligible records
- already enriched rows
- raw policy disabled
- local model unavailable
- raw-free output scan
