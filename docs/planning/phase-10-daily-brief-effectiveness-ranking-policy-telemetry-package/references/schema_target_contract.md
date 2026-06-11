# Schema Target Contract

## Versioning

Use the next schema version after local repo truth. If the prerequisite ranking/assembly slice is V51, this slice is V52.

## Required Tables

### daily_brief_exposure_events

Purpose: record raw-free metadata that a ranked/assembled brief, section, or item was exposed to the operator.

Suggested columns:

- `exposure_event_id TEXT PRIMARY KEY`
- `brief_date TEXT NOT NULL`
- `assembly_run_id TEXT`
- `ranking_run_id TEXT`
- `event_type TEXT NOT NULL`
- `section_key TEXT`
- `daily_brief_action_candidate_id TEXT`
- `rank_position INTEGER`
- `exposure_surface TEXT`
- `policy_version TEXT`
- `artifact_hash TEXT`
- `created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- full Phase 10 guard columns

No raw artifact path, markdown body, HTML body, raw title, private URL, or local path.

### daily_brief_item_outcome_events

Purpose: map post-brief lifecycle outcomes back to ranked/exposed brief items without creating lifecycle events.

Suggested columns:

- `outcome_event_id TEXT PRIMARY KEY`
- `brief_date TEXT NOT NULL`
- `daily_brief_action_candidate_id TEXT NOT NULL`
- `ranking_run_id TEXT`
- `assembly_run_id TEXT`
- `exposure_event_id TEXT`
- `lifecycle_event_id TEXT`
- `outcome_type TEXT NOT NULL`
- `outcome_lag_hours REAL`
- `rank_position INTEGER`
- `section_key TEXT`
- `candidate_family TEXT`
- `project_key TEXT`
- `source_ref_count INTEGER NOT NULL DEFAULT 0`
- `created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- full Phase 10 guard columns

### ranking_policy_eval_runs

Purpose: evaluate a ranking policy over a brief date window.

Suggested columns include window, policy/model identifiers, eval mode, candidate/outcome counts, source-ref coverage, brief usefulness score, rank-outcome score, model degradation rate, Procore noise score, created timestamp, and guard columns.

### ranking_policy_eval_items

Purpose: per-candidate evaluation facts for a policy eval run.

Suggested primary key: `(eval_run_id, daily_brief_action_candidate_id)`.

Include rank position, section, family, project, deterministic/feedback/model/final scores, model flags, outcome type/weight/lag, source-ref count, raw-free `eval_notes_json`, created timestamp, and guard columns.

### model_profile_eval_results

Purpose: aggregate local model profile reliability/utility without storing raw prompt/output.

Include counts for attempts, success, schema invalid, safety withheld, timeout, unknown alias, lifecycle-excluded refs, fallback, latency, advisory adoption proxy, created timestamp, and guard columns.

### brief_effectiveness_rollups

Purpose: raw-free daily/window/project/family/source/model trend reporting.

Include rollup scope/key, window, counts, rates, usefulness, rank-outcome, source-ref coverage, Procore noise, model degradation, duplicate proxy, feedback lift, created timestamp, and guard columns.

## Idempotency

Use deterministic IDs built from stable inputs:

- `exposure_event_id`: hash of event type + brief date + run IDs + candidate/section/surface + artifact hash.
- `outcome_event_id`: hash of brief date + candidate ID + lifecycle event ID or ignored/stale synthetic key + ranking/assembly run ID.
- `eval_run_id`: hash of window + policy version + eval mode + ranking/assembly/model/calibration versions.
- `model_profile_eval_id`: hash of window + task type + model profile/name.
- `rollup_id`: hash of scope + scope key + window + policy/eval version.

## Guards

Every table must carry the exact Phase 10 guard set used by repo truth. Do not accept caller-supplied guard values in store insert methods.
