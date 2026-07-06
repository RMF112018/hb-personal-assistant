# Claim-Candidate Ingestion Proof

For `claim_extraction` jobs the worker validates the model result (structure, provenance, bounded
evidence, confidence, unsupported-claim rejection), then ingests via the N8C-4 seam:
`claim_repository.ingest_candidates(..., extracted_by="future_qwen", model_name="qwen2.5:14b",
status="candidate", review_state="unreviewed", extractor_version="claim_extraction-v1")`.

Proven (`test_run_once_claim_extraction_ingests_candidate_unreviewed`): resulting claims are all
`status=candidate`, `review_state=unreviewed`, `extracted_by=future_qwen`, `model_name=qwen2.5:14b`,
and source-backed (`source_id` set). No auto-accept; no decision/preference/open-loop promotion; no
vault mutation. Writes go only through the validated claim repository path — never a raw INSERT.
