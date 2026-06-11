# 04 — Persistence & Source Refs

Idempotent upserts only; deterministic ids. Real-data `/tmp` copy, owner-configured:

- daily-brief candidates persisted: 4
- candidate_source_refs: 8
- by section: {"follow_up": 4}
- **daily-brief source-ref coverage: 1.0** (4/4)
- idempotency replay (run2 == run1 counts): **True**

Unit tests also prove: dry-run writes nothing; second apply adds no rows; commitments route to
`commitment_candidates` (actors user + other), never into `task_candidates`; every daily-brief
candidate carries an `email_*` source ref.
