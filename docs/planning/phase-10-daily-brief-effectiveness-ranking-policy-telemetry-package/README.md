# Phase 10 — Daily Brief Effectiveness Evaluation, Ranking Policy Telemetry, and Feedback Calibration Dashboard

## Objective

Implement the next Phase 10 enhancement for `RMF112018/hb-personal-assistant`:

**Add a deterministic, raw-safe, observational evaluation layer that measures whether ranked and assembled daily briefs are becoming more useful over time.**

The local code agent must execute this package as a one-shot implementation package with:

```bash
Execute the objective defined at docs/planning/phase-10-daily-brief-effectiveness-ranking-policy-telemetry-package/README.md
```

This package is implementation guidance only. It does not authorize external writeback, production DB mutation during validation, email sending, email drafting, calendar mutation, Graph/Procore writes, lifecycle state changes, source-ref changes, or raw private-content exposure.

## Critical Repo-Truth Contradiction

The original target assumes the prior slice, `Phase 10 — Ollama-Assisted Feedback-Calibrated Candidate Ranking and Daily Brief Assembly`, has already been implemented and validated.

Generation-time repo truth from GitHub `main` did **not** show that slice. `LATEST_SCHEMA_VERSION` was still V50 and expected ranking/assembly symbols were absent. Therefore this package is structured to be run **after** that prerequisite slice is present in the local working tree.

Decision rule:

- If local repo truth contains ranking/assembly tables/read models, implement this slice at `LATEST_SCHEMA_VERSION + 1`.
- If local repo truth still matches V50 and no ranking/assembly tables exist, stop before coding and write raw-free evidence with status `missing_ranking_assembly_prerequisite`.
- If the ranking/assembly slice exists but uses different names/schema version, adapt join paths to repo truth and preserve this package's authority, safety, and metric contracts.

## Background

Phase 10 has established a local, source-linked, raw-safe construction intelligence pipeline:

- V41 local action intelligence substrate and daily-brief candidate tables.
- V45 email follow-up raw enrichment and review-safe structures.
- V49 email/calendar raw-to-structured projection.
- V50 cross-family candidate lifecycle, review queue, merge, suppression, and feedback read model.
- Expected prerequisite V51 or later ranking/assembly overlay with deterministic-first ranking, local-only bounded Ollama advisory metadata, grouping, duplicate/similarity advice, ranking policy metadata, and source-linked assembly sections.

This slice does **not** make the model more authoritative. It measures outcomes.

## Implementation Scope

Build a closed-loop telemetry/evaluation layer that answers, raw-safely:

1. Which surfaced items were accepted, rejected, snoozed, merged, suppressed, closed, reopened, stale, or ignored?
2. Did higher-ranked items receive better operator outcomes?
3. Did model-assisted ranking outperform deterministic-only ranking, based on available observational data?
4. Which ranking policy, assembly policy, feedback calibration version, model profile, or model name correlates with better outcomes?
5. Which candidate families and Procore-derived signals are noisy or over-prioritized?
6. Which sections create useful follow-up versus clutter?
7. Were briefs useful, degraded, stale, thin, or under-supported?
8. Did source-ref coverage remain intact?
9. Did feedback calibration appear to improve or harm ranking?
10. Did duplicate/similarity advice reduce clutter or produce false duplicate noise?
11. How often was local model advice withheld, degraded, invalid, unsafe, timed out, or unused?
12. What safe, measurable next tuning actions should be recommended?

## Explicit Out of Scope

- No model autonomy.
- No automatic tuning.
- No external telemetry service.
- No lifecycle mutation from telemetry.
- No source-ref mutation from telemetry.
- No auto-accept/reject/snooze/merge/suppress/close/reopen.
- No external writeback.
- No raw/private content in telemetry, reports, logs, evidence, tests, markdown, JSON, stdout, or DB telemetry tables.
- No use of `include_raw` daily-brief rendering for telemetry.
- No production DB apply validation.
- No scheduled integration as the first implementation step. On-demand read-only CLI first; optional scheduled read-only integration only after safety proof.

## Package Structure

```text
docs/planning/phase-10-daily-brief-effectiveness-ranking-policy-telemetry-package/
  README.md
  TRIGGER_PROMPT.md
  SCOPE_LOCKS.md
  VALIDATION_MATRIX.md
  FINAL_HANDOFF_TEMPLATE.md
  PACKAGE_MANIFEST.json
  prompts/
    00_repo_truth_audit.md
    01_ranking_assembly_prerequisite_audit.md
    02_schema_migration_contract.md
    03_telemetry_join_contract.md
    04_store_repository_accessors.md
    05_exposure_event_tracking.md
    06_outcome_event_derivation.md
    07_effectiveness_packet_builder.md
    08_metric_engine.md
    09_ranking_policy_evaluator.md
    10_model_profile_evaluator.md
    11_procore_noise_and_source_family_evaluator.md
    12_rollups_and_report_dashboard.md
    13_cli_integration.md
    14_raw_safety_and_no_leak_hardening.md
    15_validation_and_evidence.md
    16_final_handoff.md
  references/
    repo_truth_audit_summary.md
    schema_target_contract.md
    design_contract.md
    metric_definitions.md
    join_path_contract.md
    raw_safety_policy.md
    evaluation_authority_contract.md
    procore_noise_metric_contract.md
    model_profile_eval_contract.md
    dashboard_report_contract.md
    evidence_bundle_manifest.md
  templates/
    db_copy_validation_commands.md
    raw_safe_sql_checks.sql
    no_raw_leak_scan.md
    evidence_index_template.md
    merge_readiness_checklist.md
    effectiveness_report_template.md
    cli_json_contract_example.json
```

## Execution Order

The local code agent must execute the prompts in numeric order:

1. `prompts/00_repo_truth_audit.md`
2. `prompts/01_ranking_assembly_prerequisite_audit.md`
3. `prompts/02_schema_migration_contract.md`
4. `prompts/03_telemetry_join_contract.md`
5. `prompts/04_store_repository_accessors.md`
6. `prompts/05_exposure_event_tracking.md`
7. `prompts/06_outcome_event_derivation.md`
8. `prompts/07_effectiveness_packet_builder.md`
9. `prompts/08_metric_engine.md`
10. `prompts/09_ranking_policy_evaluator.md`
11. `prompts/10_model_profile_evaluator.md`
12. `prompts/11_procore_noise_and_source_family_evaluator.md`
13. `prompts/12_rollups_and_report_dashboard.md`
14. `prompts/13_cli_integration.md`
15. `prompts/14_raw_safety_and_no_leak_hardening.md`
16. `prompts/15_validation_and_evidence.md`
17. `prompts/16_final_handoff.md`

Do not skip prompts. If a prompt identifies a blocking repo-truth contradiction, stop and hand off a raw-free blocker report.

## Required Deliverables

### Schema

Add the next schema version after repo truth. If the ranking/assembly prerequisite is V51, this slice should be V52.

Recommended additive tables:

1. `daily_brief_exposure_events`
2. `daily_brief_item_outcome_events`
3. `ranking_policy_eval_runs`
4. `ranking_policy_eval_items`
5. `model_profile_eval_results`
6. `brief_effectiveness_rollups`

Every table must carry the full Phase 10 guard column set with `DEFAULT 0 CHECK(... = 0)`. Do not create raw-content exempt tables.

### Modules

Add under `src/hb_assistant/construction/second_brain/local_ai/`, adjusted to repo truth:

- `daily_brief_effectiveness_packets.py`
- `daily_brief_effectiveness_metrics.py`
- `ranking_policy_evaluator.py`
- `model_profile_evaluator.py`
- `procore_noise_evaluator.py`
- `effectiveness_rollups.py`
- `daily_brief_effectiveness_report.py`

### CLI

Add under the repo-true daily-brief CLI group:

```bash
hb-assistant second-brain daily-brief evaluate-effectiveness   --window-start YYYY-MM-DD   --window-end YYYY-MM-DD   --dry-run   --json
```

Required option posture:

- `--dry-run` default.
- `--apply` requires explicit `--max-persist`.
- `--db PATH` allowed and required for validation on `/tmp` DB copies.
- Invalid windows exit `2`.
- Safety/schema/raw-leak contradictions exit `3`.
- Dry-run writes zero rows.

### Tests

Add tests matching repo layout. Generation-time repo truth shows flat `tests/` layout, so default to flat names unless local audit shows otherwise.

Required focused test files:

- `tests/test_phase_10_daily_brief_effectiveness_schema.py`
- `tests/test_phase_10_daily_brief_effectiveness_packets.py`
- `tests/test_phase_10_daily_brief_effectiveness_metrics.py`
- `tests/test_phase_10_ranking_policy_evaluator.py`
- `tests/test_phase_10_model_profile_evaluator.py`
- `tests/test_phase_10_procore_noise_evaluator.py`
- `tests/test_phase_10_effectiveness_rollups.py`
- `tests/test_phase_10_daily_brief_effectiveness_cli.py`
- `tests/test_phase_10_daily_brief_effectiveness_report.py`

### Evidence

Create raw-free evidence under:

`docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/`

Use the manifest in `references/evidence_bundle_manifest.md`.

## Acceptance Criteria

The slice is complete only when:

- It is grounded in fresh repo truth.
- It stops honestly if ranking/assembly prerequisite tables are absent.
- It adds only additive schema changes.
- It preserves lifecycle, ranking, source-ref, model, and human-review authority boundaries.
- It evaluates deterministic-only and model-assisted runs when data exists.
- It never treats absent feedback as success.
- It marks small samples as insufficient.
- It includes Procore noise metrics.
- It includes source-ref coverage metrics.
- It includes model profile reliability metrics.
- It includes feedback calibration impact metrics.
- It includes duplicate/similarity precision proxy metrics.
- It includes daily/window/project/family/source/model rollups.
- It adds CLI/report output that is raw-free and scanner-clean.
- Dry-run writes zero rows.
- Apply requires explicit `--max-persist` and is validated only on `/tmp` DB copies.
- Production DB SHA remains unchanged.
- Focused pytest, compile, Ruff, and mypy pass or documented quarantines are explicitly raw-free and justified.

## Repo-Truth Anchors

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
