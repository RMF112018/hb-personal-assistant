# Phase 10 V50 — Candidate Lifecycle, Review Queue & Feedback Read Model

Status: implemented (branch `feature/phase-10-candidate-lifecycle-review-queue`).
Source package: `docs/planning/phase-10-candidate-lifecycle-review-queue-package/`.
Evidence: `docs/evidence/phase-10-candidate-lifecycle-review-queue/`.

## Problem

Phase 10 produced candidates (`task_candidates`, `commitment_candidates`,
`daily_brief_action_candidates`), promoted accepted ones into `accepted_tasks` /
`accepted_commitments`, and scanned them into `follow_up_watch_items`. But review state was
**per-family and shallow**: `candidate_review.py` only handled task/commitment
accept/reject/ignore/snooze, and `candidate_review_events` was scoped to those two families. There
was no unified raw-safe review queue, no cross-family lifecycle (merge, group suppression,
close/reopen across daily-brief/accepted/watch), and no feedback read model. The daily brief and
usefulness gate could not reflect dispositions they did not know about.

## Design

An **append-only lifecycle overlay** that EXTENDS — never replaces — the existing per-family review
status. The task/commitment `review_status` (V41/V43) stays canonical for those families; the
overlay adds cross-family states that no single per-family table can express. A unified read model
consumes both, so there is no dual truth. No materialized review-queue table — the queue is a
computed read model.

### Schema (migration V50, additive, append-only)

Three tables, each carrying the 13 Phase-10 guard columns (`CHECK(<col>=0)`):

- `candidate_lifecycle_events` — append-only event log spanning all six families. Idempotent:
  `lifecycle_event_id` is derived from `idempotency_key` and inserts are
  `ON CONFLICT(idempotency_key) DO NOTHING`. Carries `subject_type/id`, `event_type`,
  `prior_state/new_state`, `reason_code`, bounded `reason_redacted`, `effective_until_utc`,
  `target_subject_*`, `duplicate_group_key`.
- `candidate_merge_links` — source→target merge links (idempotent by key).
- `candidate_suppression_rules` — candidate- or group-scoped suppression; reversible via an
  `active` flag (auditable; never deletes a candidate).

`LATEST_SCHEMA_VERSION` advanced 49 → 50. V1–V49 untouched; re-apply is a no-op.

### Canonical states + precedence

`source_missing > merged > suppressed > rejected > snoozed(future) > closed >
project_review_required > needs_review > stale > accepted > new`
(`references/lifecycle_state_contract.md`). The resolver gathers a subject's applicable states
(per-family base ∪ overlay disposition ∪ structural flags: source-missing, project-review,
snooze-future, suppressed, merged) and picks the highest-precedence member. A returned snooze
(effective_until in the past) falls back to `needs_review`.

### Modules (`src/hb_assistant/construction/second_brain/local_ai/`)

- `candidate_lifecycle.py` — state contract, subject context resolver, disposition operations
  (accept/reject/snooze/close/reopen/merge/suppress) and `promote`. Task/commitment accept/reject/
  snooze delegate to the existing `candidate_review` service (review_status stays canonical) and
  mirror a lifecycle event. Acceptance + promotion are **source-ref gated** (a source-missing
  actionable subject is blocked, never silently accepted). `scrub_note` strips URLs/emails/tokens/
  HTML from operator notes and is reused to defensively re-scrub already-redacted DB text.
- `candidate_lifecycle_duplicates.py` — deterministic `duplicate_group_key` via ordered fallbacks
  (source ref hash → stable key → family+project+normalized-title-hash+due → singleton); never
  hashes raw text.
- `candidate_lifecycle_read_model.py` — the unified raw-safe review queue
  (`references/review_queue_contract.md` row shape). Single-pass via a precomputed index. Default
  view = to-review states only; `include_hidden` returns all. A promoted candidate is deduped
  against its `accepted_*` row.
- `candidate_lifecycle_feedback.py` — deterministic raw-safe feedback summary (counts, rates,
  reason codes, confidence buckets, duplicate groups, project resolution).
- `candidate_lifecycle_daily_brief.py` — lifecycle-aware daily-brief sections (new/accepted/
  waiting/commitments/stale/snoozed-returning/project-review/source-missing-withheld; hidden states
  counted only) and `lifecycle_stage_context` for the usefulness gate.

### Store helpers (`construction/store/repositories.py`)

`insert_lifecycle_event` (idempotent), `list_lifecycle_events`, `latest_lifecycle_states`,
`lifecycle_counts_by_state`, `upsert_merge_link`, `list_merge_links`, `upsert_suppression_rule`
(reversible), `list_suppression_rules`. All follow the existing connection/transaction +
deterministic-id + guard-omission conventions.

### Usefulness gate

`evaluate_usefulness_gate` gained an opt-in `lifecycle_context` parameter (None → every lifecycle
check skipped, keeping legacy/empty callers hermetic). `daily_run.py` computes
`lifecycle_stage_context` on apply runs and passes it. Lifecycle contradictions
(`accepted_actions_missing_source_refs`, `lifecycle_source_ref_coverage_below_100`,
`duplicate_inflation`, `rejected/suppressed/merged_visible_as_new`, `snoozed_visible_before_return`,
`lifecycle_read_model_empty_with_candidates`, `lifecycle_stage_failed`) fail a would-be success.

### CLI (`cli/second_brain.py`)

New additive `second-brain candidates` Typer group: `review` (`--include-hidden`), `show`,
`accept`, `reject`, `snooze`, `close`, `reopen`, `merge`, `suppress`, `promote`, `feedback`. Each
operates only on the passed `--db`, emits raw-safe JSON, and is idempotent. `--now-utc/--as-of`
supports deterministic snooze/return testing. Exit codes: 0 ok, 2 invalid/blocked, 3 not-found.
The existing `second-brain review` verbs are unchanged.

## Guardrails

No production-DB mutation (validation on `/tmp` copies; prod SHA proven unchanged). No external
writeback. Guard columns stay 0 (`CHECK(=0)`). No candidate deletion as a lifecycle substitute.
Source refs remain the acceptance gate. Only redacted/bounded text, reason codes, hashes, ids, and
states are emitted — no raw bodies/HTML/URLs/recipients/tokens/prompts/responses/Procore blobs.
