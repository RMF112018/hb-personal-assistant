# Final Output — Quality-Gate Persistence (operator view)

Scenario (temp DB): two source-linked accepted tasks scanned with `--apply` (max_persist=5).

| accepted_id | classification input | quality_flags | persisted? |
|-------------|----------------------|---------------|------------|
| …:contra | status=done + waiting_on_others + no completion | `["contradictory"]` | **NO — skipped (quality_flags)** |
| …:clean  | waiting_on_me / open | none | YES → watch_status `waiting_on_me` |

Summary: `scanned=2 · skipped_quality_flags=1 · persisted=1 · status_events_written=1`.
Watch table after apply: 1 row (`watch:acc-task:clean`). The contradictory item is never
persisted as actionable, matching the report's `needs_review` routing.

Full machine-readable proof: `quality-gate-persistence-proof.json`.
