# No Auto-Start / No Vault Mutation / No Raw-DB Mutation Proof

- No auto-start: the worker has no FastAPI-lifespan / scheduler / watcher hook. Proven —
  `test_backend_startup_enqueues_no_jobs` (create_app lifespan runs; enrichment jobs count == 0);
  `test_worker_not_referenced_by_lifespan_or_automation` (api.py never imports `qwen_worker`; the
  watcher/automation files never reference the enrichment layer). Importing the modules writes nothing.
- No raw/import mutation: `enrichment_repository` writes only `assistant_enrichment_jobs` /
  `assistant_enrichment_receipts` (static write-target scan proven). claim_extraction ingestion writes
  only the N8C-4 claim tables via the validated repository.
- No vault mutation: backlink suggestions are stored in the receipt only; the worker never writes the
  vault. Proven — `test_backlink_stores_receipt_no_vault_mutation` (vault file set unchanged).
