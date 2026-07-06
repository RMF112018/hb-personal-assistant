# Job Lifecycle + Atomic Lease Proof

Lifecycle: queued -> claimed -> running -> {completed | stale | failed}; failed-with-attempts-left
-> queued. `claimed`/`running` both hold a reclaimable lease. (`skipped`/`cancelled` reserved
operator states.)

- `queue_job`: idempotent — same (job_type, source_id, note_rel_path, payload_key) => same job_id;
  a still-queued job is refreshed in place, an in-flight/terminal job is left untouched. Proven:
  re-queue returns `created=False`, count stays 1.
- `claim_next_job`: ATOMIC — `UPDATE ... WHERE job_id=? AND status='queued'` + rowcount guard. Proven
  (`test_atomic_claim_two_workers_one_job`, `test_atomic_claim_separate_connections`): with one
  queued job, worker A claims it and worker B gets `None`.
- `heartbeat_job`: extends `lease_expires_at` for the owner only (wrong owner -> False).
- `release_expired_leases`: requeues claimed/running jobs whose lease is in the past (owner cleared).
- `complete_job`: owner-checked; a rogue worker completing returns False (no overwrite). Writes the
  receipt in the same transaction.
- `fail_job`: requeues while attempts remain, else marks `failed`; writes a `failed` receipt per
  attempt. Proven: attempt1<max -> requeued; attempt==max -> failed; 2 receipts.
