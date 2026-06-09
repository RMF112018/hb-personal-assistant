# Candidate Row-Count Proof

DB: `/tmp/hb_daily_brief_intelligence_test.sqlite` (copy of the **(Dev)** app-support DB, schema V44).
Table: `daily_brief_action_candidates`, `brief_date='2026-06-09'`.

| Stage | total rows | delta |
| --- | --- | --- |
| Baseline (fresh copy) | 20 | — |
| After standalone intelligence (dry-run) | 20 | 0 |
| After daily-run **dry-run** `--with-intelligence` | 20 | 0 (dry-run persists nothing) |
| After daily-run **apply** `--with-intelligence` | 20 | 0 (no new eligible candidates; existing rows already materialized) |
| After daily-run **apply #2** (idempotency) | 20 | 0 (no duplication) |

Interpretation: dry-run never persists. Apply ran all 5 generation stages (`stages_ok=5`,
`total_persisted=0`) — the date's candidates were already materialized in the source Dev DB, so apply
is correctly **idempotent** (re-running adds nothing). Bounded persistence + per-stage/global caps and
the seeded-data persist/idempotency mechanics are covered by `tests/test_phase_10_pipeline.py` and
`tests/test_phase_10_daily_brief_synthesis.py` (capped writes, `skipped_existing`).

`local_model_run_receipts`: 1 (baseline) → 2 (after apply `--with-intelligence`, which wrote one
**hash-only** receipt; guard columns 0). Dry-run intelligence wrote no receipt.
