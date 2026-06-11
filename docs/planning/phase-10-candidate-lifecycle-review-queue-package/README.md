# Phase 10 — Candidate Lifecycle, Review Queue, and Feedback Read Model

## Objective

Build the next Phase 10 enhancement: a deterministic, source-linked, raw-safe lifecycle and review-control layer that turns existing daily-brief, task, follow-up, and commitment candidates into an operator-managed system.

The finished implementation must let Bobby review, accept, reject, snooze, merge, close, suppress recurring duplicates, reopen, and audit candidate outcomes locally, then feed those outcomes into the daily brief, usefulness gate, and future extractor/ranking read models.

The local code agent must be able to execute this package with:

```bash
Execute the objective defined at docs/planning/phase-10-candidate-lifecycle-review-queue-package/README.md
```

## Background / repo-truth assumptions

This package is based on a repo-truth audit of current `main` through the GitHub connector. The local agent must re-run the repo-truth audit before editing, because local `main`, origin, schema version, and production DB counts may have changed.

Observed repo truth at package generation:

- Phase 10 V41 already created the core tables: `task_candidates`, `commitment_candidates`, `candidate_source_refs`, `candidate_review_events`, `accepted_tasks`, `accepted_commitments`, `follow_up_watch_items`, `follow_up_status_events`, and `daily_brief_action_candidates`.
- Phase 10A already added candidate review metadata (`reviewed_utc`, `reviewed_by`, `review_note_redacted`, `snoozed_until_utc`) to task/commitment candidates and event metadata to `candidate_review_events`.
- `local_ai/candidate_review.py` already implements task/commitment review list/show/summary plus accept/reject/ignore/snooze/edit/export service logic.
- `second-brain review` already has read-only and mutation CLI verbs for task/commitment candidates, including batch mode for accept/ignore/reject.
- Explicit candidate promotion exists for task candidates through `phase-10 review-candidate --promote`; the local agent must verify whether commitment promotion and source-ref propagation are complete before extending.
- `follow_up_watch.py` already scans accepted tasks/commitments into deterministic watch states after acceptance.
- `daily_brief_context_packet.py` already consumes accepted tasks, accepted commitments, follow-up watch items, and source-ref-gated daily-brief action candidates.
- `usefulness_gate.py` already checks source-ref coverage and several daily-brief contradictions, including email-follow-up stage health.
- The latest email-follow-up projection slice appears present on `main` and uses structured email/thread read models to write domain candidates and daily-brief rows through `persist_candidate_with_refs`.

Important interpretation:

The implementation should **not rebuild the existing Phase 10A task/commitment review CLI**. It should converge and extend it into a unified lifecycle/read-model layer that includes `daily_brief_action_candidates`, accepted actions, follow-up watches, duplicate/merge/suppression state, and feedback summaries.

## Scope

Implement, test, and document:

1. A repo-truth lifecycle audit.
2. A unified raw-safe candidate lifecycle/review read model.
3. A lifecycle state contract across candidate/domain/read-model families.
4. Local-only disposition operations: accept, reject, snooze, merge, close, reopen, duplicate, suppress.
5. Promotion and accepted-item source-ref preservation.
6. Duplicate group detection and merge/suppression rules.
7. A structured feedback read model derived from disposition/lifecycle outcomes.
8. Daily-brief lifecycle integration.
9. Usefulness-gate lifecycle contradiction checks.
10. CLI/local operator surface, preferably additive under `hb-assistant second-brain candidates ...` unless repo truth proves extending `second-brain review` is cleaner.
11. Raw-safety and no-leak hardening.
12. `/tmp` DB-copy validation and raw-free evidence.

## Recommended implementation strategy

Use repo truth to decide, but start from this preferred shape:

### Preferred data model

Use an append-only lifecycle overlay for cross-family state.

Existing task/commitment review status remains canonical for task/commitment candidate status. New lifecycle events extend cross-family behavior, not silently replace existing review status.

Add a minimal schema migration **only if the repo-truth audit confirms no existing table can cleanly represent these cross-family states**. Expected minimal VNext additions:

- `candidate_lifecycle_events`
- `candidate_merge_links`
- `candidate_suppression_rules`

Do **not** add a materialized review queue table unless the audit proves an immutable table is required. Prefer a read model built from candidate/domain tables plus lifecycle overlays.

### Preferred modules

Candidate module names are suggestions; the local agent may adjust to existing conventions.

```text
src/hb_assistant/construction/second_brain/local_ai/
  candidate_lifecycle.py
  candidate_lifecycle_read_model.py
  candidate_lifecycle_feedback.py
  candidate_lifecycle_duplicates.py
  candidate_lifecycle_daily_brief.py
```

Expected store additions should live in the existing construction store layer, preserving local-only DB access and transaction conventions.

### Preferred CLI

```bash
hb-assistant second-brain candidates review --db <copy> --json
hb-assistant second-brain candidates show <subject-id> --subject-type <type> --db <copy> --json
hb-assistant second-brain candidates accept <subject-id> --subject-type <type> --db <copy> --json
hb-assistant second-brain candidates reject <subject-id> --subject-type <type> --reason <code> --db <copy> --json
hb-assistant second-brain candidates snooze <subject-id> --subject-type <type> --until YYYY-MM-DD --db <copy> --json
hb-assistant second-brain candidates merge <source-id> <target-id> --source-type <type> --target-type <type> --db <copy> --json
hb-assistant second-brain candidates close <subject-id> --subject-type <type> --db <copy> --json
hb-assistant second-brain candidates reopen <subject-id> --subject-type <type> --db <copy> --json
hb-assistant second-brain candidates suppress <subject-id-or-group-key> --scope candidate|group --reason <code> --db <copy> --json
hb-assistant second-brain candidates feedback --db <copy> --json
```

If repo truth shows `second-brain review` is the intended namespace, keep existing verbs stable and add only non-breaking subcommands/aliases.

## Explicit out of scope

- No production DB mutation during validation.
- No live Graph, Procore, email, calendar, SharePoint, OneDrive, Obsidian, or external writeback.
- No email sending or drafting.
- No calendar event mutation.
- No cloud LLM use on private raw content.
- No raw body/HTML/calendar description/Procore payload/model prompt/model response exposure.
- No destructive candidate deletion as a lifecycle substitute.
- No broad rewrite of email/procore/calendar extraction.
- No automatic external task creation.
- No hidden acceptance of source-ref-missing candidates.
- No schema changes unless the audit proves they are required.

## Expected final behavior

The system should produce a raw-safe review queue where every visible row clearly states:

- subject ID and subject type
- family / source family
- lifecycle state
- review status or accepted/watch status
- title/reason/next action, already redacted and bounded
- confidence / priority
- project key or `project_review_required`
- source-ref count and source-ref coverage
- duplicate group key
- age/staleness/due bucket
- review reason and disposition reason
- whether it is hidden, snoozed, suppressed, merged, accepted, closed, or actionable

The daily brief should:

- Show new review items that are actionable and source-linked.
- Show accepted actions and stale watch items distinctly.
- Show waiting-on-others and user commitments distinctly.
- Hide rejected/suppressed/merged duplicates from normal view.
- Reintroduce snoozed items only on/after return date.
- Surface project-review-required items honestly.
- Degrade or fail closed when source refs are missing for surfaced candidates.
- Emit lifecycle/status cards when lifecycle stages fail or data is withheld.

## Package structure

```text
docs/planning/phase-10-candidate-lifecycle-review-queue-package/
  README.md
  TRIGGER_PROMPT.md
  SCOPE_LOCKS.md
  VALIDATION_MATRIX.md
  FINAL_HANDOFF_TEMPLATE.md
  prompts/
    00_repo_truth_audit.md
    01_schema_and_lifecycle_contract_audit.md
    02_review_queue_read_model.md
    03_lifecycle_event_store_or_state_model.md
    04_candidate_disposition_operations.md
    05_candidate_promotion_to_accepted_actions.md
    06_duplicate_merge_and_suppression.md
    07_feedback_read_model.md
    08_daily_brief_lifecycle_integration.md
    09_usefulness_gate_and_status.md
    10_cli_or_local_operator_surface.md
    11_raw_safety_and_no_leak_hardening.md
    12_validation_and_evidence.md
    13_final_handoff.md
  references/
    lifecycle_state_contract.md
    review_queue_contract.md
    disposition_reason_codes.md
    promotion_contract.md
    source_ref_propagation_contract.md
    duplicate_merge_contract.md
    feedback_read_model_contract.md
    raw_safety_policy.md
    expected_db_invariants.md
    usefulness_scorecard.md
  templates/
    db_copy_validation_commands.md
    raw_safe_sql_checks.sql
    lifecycle_validation_sql.sql
    no_raw_leak_scan.md
    evidence_index_template.md
    merge_readiness_checklist.md
```

## Ordered execution sequence

Run prompts in order. Do not skip the audit prompts.

1. `prompts/00_repo_truth_audit.md`
2. `prompts/01_schema_and_lifecycle_contract_audit.md`
3. `prompts/02_review_queue_read_model.md`
4. `prompts/03_lifecycle_event_store_or_state_model.md`
5. `prompts/04_candidate_disposition_operations.md`
6. `prompts/05_candidate_promotion_to_accepted_actions.md`
7. `prompts/06_duplicate_merge_and_suppression.md`
8. `prompts/07_feedback_read_model.md`
9. `prompts/08_daily_brief_lifecycle_integration.md`
10. `prompts/09_usefulness_gate_and_status.md`
11. `prompts/10_cli_or_local_operator_surface.md`
12. `prompts/11_raw_safety_and_no_leak_hardening.md`
13. `prompts/12_validation_and_evidence.md`
14. `prompts/13_final_handoff.md`

## Validation requirements

Minimum validation:

```bash
python -m compileall src tests
ruff check src tests
pytest tests/test_phase_10a_candidate_review.py tests/test_phase_10a_candidate_review_cli.py
pytest tests/test_phase_10_acceptance_promotion.py tests/test_phase_10_follow_up_monitor.py tests/test_phase_10_daily_brief_synthesis.py tests/test_phase_10_usefulness_gate.py
```

Add and run new focused tests, expected names:

```bash
pytest tests/test_phase_10_candidate_lifecycle_read_model.py
pytest tests/test_phase_10_candidate_lifecycle_operations.py
pytest tests/test_phase_10_candidate_duplicate_merge.py
pytest tests/test_phase_10_candidate_lifecycle_daily_brief.py
pytest tests/test_phase_10_candidate_lifecycle_usefulness_gate.py
pytest tests/test_phase_10_candidate_lifecycle_cli.py
pytest tests/test_phase_10_candidate_lifecycle_no_raw_leak.py
```

DB validation must use `/tmp` DB copies only.

## Evidence requirements

Create raw-free evidence under a new evidence root, for example:

```text
docs/evidence/phase-10-candidate-lifecycle-review-queue/
  00_repo_truth.md
  01_schema_audit.json
  02_review_queue_sample.json
  03_lifecycle_transition_matrix.json
  04_promotion_source_ref_proof.json
  05_duplicate_merge_idempotency.json
  06_feedback_summary.json
  07_daily_brief_lifecycle_output.md
  08_usefulness_gate_lifecycle.json
  09_no_raw_leak_scan.json
  10_db_copy_validation.md
  11_final_handoff.md
```

All evidence must be raw-safe. Do not include full email subjects, bodies, HTML, recipients, attendees, URLs, tokens, prompt text, model responses, or raw Procore detail blobs.

## Stop conditions

Stop and report rather than forcing implementation if any of these occur:

- Production DB would be mutated during validation.
- A live external writeback path is required.
- Source refs are missing for surfaced actionable candidates and no fail-closed path exists.
- A schema migration is required but cannot be made additive/idempotent enough for SQLite migration conventions.
- Existing task/commitment review behavior would be broken.
- The no-raw-leak scan finds raw body/HTML/URL/token/model-prompt/model-response output.
- Lifecycle stages fail but the daily brief would still report success.
- The implementation would need cloud LLM processing over private raw content.

## Final handoff requirements

Use `FINAL_HANDOFF_TEMPLATE.md` exactly. Include branch, commit SHA, changed files, tests, DB-copy results, lifecycle counts, source-ref coverage, project-key coverage, duplicate/idempotency proof, guard-column result, no-raw-leak result, usefulness-gate result, and merge-readiness statement.

