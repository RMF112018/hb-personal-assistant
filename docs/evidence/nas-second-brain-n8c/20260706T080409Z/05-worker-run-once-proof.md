# Worker run_once Proof (FakeModelProvider)

`qwen_worker.poll_and_process(db_path, provider, worker_id, limit, dry_run)` — invoked only by the
CLI or a test. With `FakeModelProvider` (no live Ollama):
- source_summary -> job `completed`, receipt `stored_only`, no claims created.
- claim_extraction -> job `completed`, receipt `candidate_claims_ingested`, candidate claim(s) created.
- Receipts carry runtime=fake, model_name=qwen2.5:14b, prompt_version, and non-empty input_digest +
  output_digest (sha256 of prompt / raw output).
- `dry_run=True` is READ-ONLY: peeks the next job, previews (`would_complete`), and persists nothing
  (job stays queued+unleased, zero receipts, zero claims).
CLI: `hb-assistant qwen-worker run-once|run-batch|status`, default `--dry-run` (writes need `--apply`).
