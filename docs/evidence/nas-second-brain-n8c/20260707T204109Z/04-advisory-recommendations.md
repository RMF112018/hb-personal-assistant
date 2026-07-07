# 04 — Advisory Recommendations (no review disposition)

## Advisory-only, operator-review-required
Every recommendation row is pinned at the schema level to `review_policy = 'advisory_review_loop'` and
`requires_operator_review = 1` (CHECK equality — a row physically cannot claim it applies a disposition).
The models mirror this: `FeedbackRecommendation.to_row()` always emits those two values, and the derivation
map contains only `suggest_*` / `operator_note` types — never accept/reject/defer/dispose.

## Never a state change
- Capturing feedback writes only the five feedback-owned tables (proven by the snapshot-before/after
  rowcount tests in `test_feedback_repository.py::test_upsert_writes_only_feedback_tables` and
  `test_feedback_service.py::test_apply_mutates_no_upstream_table`).
- A `wrong_review_label` or `candidate_should_be_trusted` feedback produces a `suggest_review` /
  `suggest_relabel_trusted` **suggestion** — it does NOT relabel the review item or convert a candidate to
  trusted.
- `useful` feedback produces no recommendation and emits no `recommended` event.

## Bounded + redaction-safe
- Notes bounded to `NOTE_HARD_CAP` (2000), rationales to `RATIONALE_HARD_CAP` (500), ids/refs bounded,
  ≤ `MAX_TARGETS` (50) / ≤ `MAX_RECOMMENDATIONS` (50).
- Targets carry only whitelisted anchor ids (`TARGET_ANCHOR_FIELDS`) — unknown/non-scalar anchors are
  dropped by `normalized_anchors()`.
- Export (`feedback_export_v1`) carries bounded metadata + ids only; the API/CLI/MCP tests assert no
  `claim_text` / `evidence_excerpt` / `email_body` / raw-response / prompt leakage.
