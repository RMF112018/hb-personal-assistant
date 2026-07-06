# N8C-4 Baseline + Carry-Forward

N8C-4 committed locally as `0f65719a` (18/18 pre-commit checks passed, no AI co-author trailer).
Lineage: `c454a581` (N8C-1) → `319ceff0` (N8C-2) → `86701ad8` (N8C-3) → `0f65719a` (N8C-4) →
N8C-5 branch base.

Carried forward and reused (not reimplemented):
- N8C-2 identity: `source_card_identity.get_source_for_card` (ambiguity), `content_sha256` digest.
- N8C-3 navigation: `source_navigation.get_source(...)["source"]["text_excerpt"]` bounded read.
- N8C-4 claim layer: `claim_repository.ingest_candidates(..., extracted_by="future_qwen")` seam,
  `ClaimCandidate`, `bound_evidence`/`clamp_confidence`, EVIDENCE_MAX_CHARS.
- Store conventions: `assistant_claim_tables` DDL/enum/`_csv` pattern; migrator guarded-block +
  `_vNN_statements()` pattern; `borrow_connection`/`transaction` repository pattern.
