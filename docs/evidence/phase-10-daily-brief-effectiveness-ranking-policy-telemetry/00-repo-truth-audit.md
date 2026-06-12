# 00 — Repo Truth Audit (Phase 10 V52 Daily-Brief Effectiveness Telemetry)

Read-only audit run before any code change. Raw-free.

## Repo state

- Branch: `feature/phase-10-ollama-candidate-ranking-brief-assembly` (NOT `main`).
- HEAD at audit: `6938380b` (V51 Ollama-assisted ranking + daily-brief assembly overlay).
- Pre-existing dirty tree: 13 `docs/evidence/construction-intelligence-phase-07a/08b/08c/*` files
  modified before this session (foreign concurrent churn) + the untracked V52 planning package.
  Left untouched by this slice.

## Schema head

- `src/hb_assistant/store/migrator.py` declared `LATEST_SCHEMA_VERSION = 51` at audit time.
- The generation-time package anchor assumed V50/`missing_ranking_assembly_prerequisite`; **local repo
  truth is ahead** — V51 ranking/assembly is present. Per the package decision rule, this slice is
  therefore implemented at **V52** (we do not hit the missing-prerequisite stop condition).

## Ranking/assembly prerequisite symbols (present locally)

Confirmed present (V51): `daily_brief_ranking_runs`, `daily_brief_ranked_candidates`,
`candidate_similarity_edges`, `daily_brief_assembly_runs`, `daily_brief_assembly_sections`;
columns `ranking_run_id`, `assembly_run_id`, `candidate_set_hash`, `feedback_digest_hash`,
`deterministic_score`, `feedback_score`, `model_advisory_score`, `final_score`, `rank_position`,
`section_key`, `group_key`, `duplicate_cluster_id`, `model_status`, `deterministic_fallback_used`.
Store readers: `list_ranking_runs`, `list_ranked_candidates`, `list_similarity_edges`,
`list_assembly_runs`, `list_assembly_sections`.

## Lifecycle / source / model sources (read-only inputs)

- `candidate_lifecycle_read_model.py::build_review_queue(include_hidden=True)` — canonical
  cross-family disposition states (`accepted/rejected/snoozed/merged/suppressed/closed/new/
  needs_review/project_review_required/stale/source_missing`); per-row `source_family`, `family`,
  `project_key`, `source_ref_count`, `actionable`.
- `candidate_ranking_packets._candidate_id` — the namespaced candidate id V51 persisted as
  `daily_brief_action_candidate_id`; reused by V52 for the join (delegated, not forked).
- `store.list_lifecycle_events`, `store.list_local_model_run_receipts`,
  `store.list_candidate_source_refs` — outcome / receipt / source-ref metadata.

## CLI / scanner / render anchors

- CLI group `second-brain daily-brief` (`cli/second_brain.py`); `rank-candidates` is the option/exit
  template; `_redact_db_indicator` redacts home→`~`, keeps `/tmp`.
- Scanner: `model_eval_metrics.py::scan_text_for_forbidden` (category codes only).
- `daily_brief_render.render_daily_brief(include_raw=False)` — render path left untouched; V52 derives
  exposure proxies from persisted V51 rows, never from `include_raw`.

## Test layout

Flat `tests/test_phase_10_*`; shared seed helper pattern `tests/_phase_10_ranking_seed.py`.

## Decision

Ranking/assembly prerequisite IS present → implement the effectiveness telemetry slice at **V52**
(additive, observational only).
