# Repo Truth Audit Summary

## Generation-Time Summary

Generation-time repo-truth anchors from GitHub `main`:

- `src/hb_assistant/store/migrator.py` declares `LATEST_SCHEMA_VERSION = 50`.
- Latest generation-time migration is V50: `v50_phase_10_candidate_lifecycle_overlay`.
- Expected V51 ranking/assembly symbols were not present on GitHub `main` at generation time: `daily_brief_ranking_runs`, `daily_brief_ranked_candidates`, `candidate_similarity_edges`, `daily_brief_assembly_runs`, `daily_brief_assembly_sections`, `ranking_run_id`, `assembly_run_id`, `candidate_set_hash`, `feedback_digest_hash`.
- Existing Phase 10 guard convention is the 13-column `PHASE_10_GUARD_COLUMNS` set in `src/hb_assistant/construction/second_brain/local_ai/schema.py`.
- Existing V41 substrate includes `local_model_run_receipts`, `candidate_source_refs`, `daily_brief_action_candidates`, `task_candidates`, `commitment_candidates`, `accepted_tasks`, `accepted_commitments`, `follow_up_watch_items`, and `candidate_review_events`.
- Existing V50 lifecycle overlay includes `candidate_lifecycle_events`, `candidate_merge_links`, and `candidate_suppression_rules`.
- `candidate_lifecycle_read_model.py` computes the cross-family review queue/read model. Do not add a competing lifecycle truth.
- `daily_brief_render.py` renders `daily_brief_action_candidates` read-only. Its `include_raw` path is local-consumption-only and must not feed telemetry/evidence.
- `pipeline.py` is dry-run-first and apply requires an explicit cap.
- `model_eval_metrics.py::scan_text_for_forbidden` is the reusable category-only redaction scanner.

The local code agent must rerun the repo-truth audit locally before coding because Bobby's local working tree may include the already-validated ranking/assembly slice even though GitHub `main` did not at generation time.

## Required Local Re-Audit Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline --decorate -12

rg -n "LATEST_SCHEMA_VERSION|V51|V52|daily_brief_ranking_runs|daily_brief_ranked_candidates|candidate_similarity_edges|daily_brief_assembly_runs|daily_brief_assembly_sections|ranking_run_id|assembly_run_id|model_layer_status|deterministic_fallback_used|feedback_digest_hash|candidate_set_hash" src tests docs

rg -n "candidate_lifecycle|review_queue|feedback|accepted|rejected|snoozed|merged|suppressed|closed|reopened|stale|review_required|review-required|ignored|outcome|read_model" src tests docs

rg -n "daily brief|daily_brief|render|markdown|html|browser|preview|assembly|section|status_block|rank-candidates|brief_date|daily-run|daily_run" src tests docs

rg -n "deterministic_score|feedback_score|model_advisory_score|final_score|rank_position|section_key|group_key|duplicate_cluster_id|model_profile_id|model_name|model_receipt_id|model_status|degraded_reason|withheld|timeout|receipt|local_model_run_receipts|StructuredOutputClient|StaticOutputClient" src tests docs

rg -n "scan_text_for_forbidden|no-raw|raw leak|leak scan|forbidden|jwt|bearer|private_key|url|email|token|signed URL|full body|raw_content|include-raw-content|receipt_hash|prompt_hash|output_hash|evidence" src tests docs

rg -n "Typer|typer.Option|typer.Exit|# noqa: B008|daily-brief|rank-candidates|local-model status|--dry-run|--apply|--json|--db|--max-persist|_redact_db_indicator" src tests docs

find tests -maxdepth 2 -type f | sort | sed -n '1,240p'
```

## Required Repo-Truth Decisions

1. Current schema head.
2. Whether ranking/assembly prerequisite exists.
3. Actual table/read-model names for ranking runs, ranked candidates, assembly runs, assembly sections, duplicate/similarity edges, and model ranking receipts.
4. Actual CLI group to extend.
5. Actual store/repository class that should own insert/list accessors.
6. Actual no-raw scanner command and scanner helper imports.
7. Actual test layout.

## Stop Condition

If the ranking/assembly prerequisite is absent, stop before implementation and create:

`docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/00-missing-ranking-assembly-prerequisite.md`

The evidence must be raw-free and include only symbols searched, files inspected, schema head, and the blocker reason.
