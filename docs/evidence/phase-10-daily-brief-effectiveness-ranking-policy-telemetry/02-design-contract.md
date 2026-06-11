# 02 — Design Contract (as built)

## Authority hierarchy (unchanged by this slice)

Operator lifecycle decisions > existing lifecycle/read-model state > source refs (traceability) >
deterministic ranking rules > local model advice. Telemetry can **recommend** tuning actions but
**cannot apply** them. It is observational only.

## What V52 adds (additive)

- Schema V52: `daily_brief_exposure_events`, `daily_brief_item_outcome_events`,
  `ranking_policy_eval_runs`, `ranking_policy_eval_items`, `model_profile_eval_results`,
  `brief_effectiveness_rollups` — each with the 13 Phase-10 `CHECK(=0)` guard columns.
- Modules: `daily_brief_effectiveness_packets`, `daily_brief_effectiveness_metrics`,
  `ranking_policy_evaluator`, `model_profile_evaluator`, `procore_noise_evaluator`,
  `effectiveness_rollups`, `daily_brief_effectiveness_report`.
- CLI: `second-brain daily-brief evaluate-effectiveness`.

## Approved contract tightenings (applied)

1. **Exposure events are persisted V51 surfaced-item exposure proxies, not confirmed render
   impressions** — derived from the persisted `daily_brief_ranked_candidates`/assembly rows
   (`exposure_surface = persisted_ranking_overlay`); the render path is untouched.
2. **Ignored-outcome lag window explicit, default 72h** — persisted as `ignored_lag_hours` on
   outcome events and eval runs, surfaced in the report.
3. **`--max-persist` caps the TOTAL projected inserts across all six V52 tables** — if the projected
   total exceeds the cap, the run **fails closed (exit 3) before inserting anything** (no partial
   writes).
4. **No V50/V51 mutation** — apply persists only V52 rows; a before/after content-fingerprint test
   proves the lifecycle/source-ref/ranking/similarity/assembly tables are byte-identical after apply.
5. **All six V52 tables enumerated in the Phase-10 guard/schema-status surface**
   (`build_phase_10_v52_schema_status_report`), not merely created with guard columns.
6. **Missing rollup dimensions normalize to `unknown`** for stable scope keys.
7. Table-lifecycle governance classification of the V49/V50/V51/V52 tables remains **deferred
   pre-existing governance debt** — out of scope here.

## Read-only / no-writeback contract

Packet building + metric computation are pure/read-only. Apply may persist V52 telemetry rows only;
it cannot mutate candidate/lifecycle/source-ref/ranking/assembly source tables. No external/Graph/
Procore/email/calendar/SharePoint/OneDrive/Obsidian writeback. No cloud or local model call. Every
public result states it is advisory and observational. Outputs are raw-free (counts/rates/scores/
ids/hashes/reason codes/scanner category codes only).
