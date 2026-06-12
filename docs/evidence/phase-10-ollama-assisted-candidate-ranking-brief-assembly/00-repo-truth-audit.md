# Phase 10 V51 — Repo-Truth Audit

Slice: **Ollama-Assisted Feedback-Calibrated Candidate Ranking and Daily-Brief Assembly** (additive,
deterministic-first, raw-safe, local-only overlay on the V50 lifecycle slice).

## Branch base

- V50 candidate-lifecycle slice is **not yet on `origin/main`** (origin/main head = `512d103f`).
  V50 lives at `dbd4d41f` on `feature/phase-10-candidate-lifecycle-review-queue`.
- This slice branches off **`dbd4d41f`** (head schema = V50) → branch
  `feature/phase-10-ollama-candidate-ranking-brief-assembly`. Branching from `main` would have been
  stale (missing V50).

## Schema head

- `LATEST_SCHEMA_VERSION = 50` at session start (`src/hb_assistant/store/migrator.py`). This slice is
  **V51** (next version after head), purely additive.
- Plain-root prod DB on disk is at schema **49** (V50 code present but not yet applied to that file);
  SHA-256 baseline `d0c3e52a…` (unchanged across the session).

## Existing substrate reused (not duplicated)

- **Read models (V50)**: `candidate_lifecycle_read_model.build_review_queue` (unified, raw-safe join
  with lifecycle/merge/suppression overlay), `candidate_lifecycle_daily_brief` (authoritative
  deterministic brief + `lifecycle_stage_context`), `candidate_lifecycle_feedback.build_feedback_summary`.
- **Local-AI runtime**: `structured_output.StructuredOutputClient` / `StaticOutputClient`
  (schema-enforced, bounded retry, single-hop fallback, hash-only receipts in
  `local_model_run_receipts`), `model_eval_metrics.scan_text_for_forbidden`, `provider`/`model_router`,
  `retrieval.embedder.{DeterministicEmbedder,OllamaEmbedder}`.
- **Gate**: `usefulness_gate.evaluate_usefulness_gate` (extended opt-in, mirrors `lifecycle_context`).
- **Pydantic conventions**: `model_config={"extra":"forbid"}`, `Field` bounds, `Literal` enums, field
  validators (from `models.py`).

## Key repo-truth findings shaping the design

- A `daily_brief_action_candidate`'s provenance (`accepted-task|<id>` / `watch|<id>`) is encoded only
  in its `group_key`, which is **not** a stored column. Source refs live on the underlying accepted
  subject, not the dbac row. The V50 review-queue read model already resolves this correctly
  (source-required subjects carry real coverage; brief projections inherit). → The ranking overlay
  consumes the **unified review-queue rows** (real `lifecycle_state` / `source_ref_count` /
  coverage / `actionable` / `hidden`), not the provenance-stripped dbac rows. Documented deviation.
- The V50 `lifecycle_stage_context` already computes surfaced source-ref coverage exactly as needed;
  the ranking overlay mirrors and extends it.

## Deviations from the package (repo-truth-driven)

1. Schema version is **V51** (README hedged "if V50 is current, V51").
2. Tests are **flat** in `tests/` (repo truth), not nested under
   `tests/construction/second_brain/local_ai/` as the README validation block assumed. The focused
   pytest paths are the flat `tests/test_phase_10_candidate_ranking_*.py` names.
3. The construction DB filename is `hb-personal-assistant.sqlite` (resolved from `PathPolicy`), not
   `construction.db` as the README example used.
4. The ranking candidate id stored in `daily_brief_ranked_candidates.daily_brief_action_candidate_id`
   is a canonical subject id (`<subject_type>:<subject_id>`, or the `dbac-…` id for direct brief
   actions) so source-ref coverage is real per item.

## Pre-existing failures (NOT this slice)

- `test_*_tables_classified_in_lifecycle_contract` (e.g. v37) and
  `test_second_brain_no_writeback_proof::*` fail on the slice-absent base `dbd4d41f` (V49/V50
  table-lifecycle-contract debt; `reconciliation.in_db_not_in_contract != []`). Proven identical on a
  base worktree. This slice adds 5 tables to the same unclassified list with no new red/green
  transition; the contract reconciliation is intentionally deferred (separate governance PR).
- `mypy src` reports 2 errors in `review_burden_mart.py` (untouched); proven identical on base.
