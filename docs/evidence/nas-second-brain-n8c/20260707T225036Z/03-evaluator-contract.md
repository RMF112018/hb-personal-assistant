# N8C-20 — evaluator contract

`quality_evaluator.py` consumes existing N8C read-only repositories via `QualityProviders`
(`action_stage_repo`, `feedback_repo`, `draft_repo`, `packet_repo`, `review_repo`, `source_repo`, `router`;
any may be `None`). It produces `QualityFinding` objects and one `QualityTarget`. Three entrypoints:

- `preview_quality(providers, *, target_kind, target_id, conn)` — fully read-only; assembles the finding plan
  and deterministic ids, persists nothing.
- `build_quality(providers, repo, *, apply=False, conn)` — preview, then only when `apply=True` calls
  `repo.upsert_quality_run(...)` (writes the five quality tables only).
- `export_quality(repo, *, quality_run_id, limit)` — bounded read-only JSON export (header + findings +
  targets; no raw bodies, no repair/execution fields).

## Determinism / idempotency / lineage

- `target_digest` = digest over the target's stable signals (ids/status/digests/counts). A changed target →
  changed `target_digest` → changed `input_digest` → new `quality_run_id`.
- `request_digest` = digest over `(target_kind, target_id, policy_json)` — the supersede lineage key.
- Re-evaluating an unchanged target is a no-op (`reused=True`); a changed target creates a new run that
  supersedes the prior `draft`/`evaluated` run of the same lineage (a quality-owned status change only).

## Per-target-kind checks (deterministic; each maps a read surface to advisory finding types)

- **action_stage** — item with provenance but no backing citation → `missing_citation`; item `source_id`
  absent from the source index → `missing_source_ref`, index row `deleted` → `stale_source_ref`; duplicate
  item signature → `duplicate_stage_candidate`; citation referencing a missing item → `orphan_stage_citation`;
  execution-verb text → `execution_language_risk`; finality-language text → `finality_language_risk`; stage
  policy ≠ fixed policy → `policy_mismatch`.
- **feedback** — feedback policy ≠ fixed policy → `policy_mismatch`; source-related feedback with no
  source-anchored target → `missing_source_ref`; recommendation with no target → `orphan_feedback_target`;
  risky note text → execution/finality risk.
- **answer_draft** — support section with no citation → `missing_citation`; candidate section without a review
  label → `candidate_without_label`; excluded section used as support → `excluded_used_as_support`; trusted
  section whose effective review ≠ accepted → `trusted_without_accepted_review`.
- **workflow** — route with no populated sections → `workflow_section_empty`; `insufficient_context` /
  `needs_clarification` status → `insufficient_context`.
- **any unknown/absent target** — `unknown_target`.

## Advisory posture (verified)

Every run is pinned `status='evaluated'` (lifecycle only), `action_policy='no_execution'`,
`execution_policy='evaluate_only'`, `requires_operator_review=1`. Every finding row carries
`execution_policy='evaluate_only'` + `requires_operator_review=1` and NO accept/reject/defer/dispose/repair/
execute field (`test_run_and_findings_are_advisory`, `test_finding_row_has_no_disposition_field`).

## Bounds

`DETAIL_HARD_CAP=1000`, `ADVICE_HARD_CAP=500`, `MAX_FINDINGS=200`, `MAX_TARGETS=50`; over-cap text is bounded
and a truncated plan is flagged (`truncated=1`) with a `dropped_count` receipt.
