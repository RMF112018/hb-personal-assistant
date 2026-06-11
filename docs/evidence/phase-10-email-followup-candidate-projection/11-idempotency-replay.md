# 11 — Idempotency Replay

Second apply on the same `/tmp` copy produced **no new rows** (deterministic ids).

| table | run1 | run2 |
|---|---:|---:|
| task_candidates | 4 | 4 |
| commitment_candidates | 0 | 0 |
| daily_brief_action_candidates | 4 | 4 |
| candidate_source_refs | 8 | 8 |

Idempotent: **True**. Unit test
`test_apply_persists_idempotently_with_full_source_ref_coverage` proves the same on a fresh DB.
