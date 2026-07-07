# 04 — Per-Workflow Proof

Seeded a migrated temp DB with representative records (a trusted + a candidate + a rejected decision; a
preference; open loops of type open/waiting_for/candidate/stale/closed; operator-accepted + unreviewed
claims; a draft) and routed each workflow. Outcomes (also asserted in `tests/test_workflow_handlers.py`):

## daily_brief_context
`status=routed`, `workflow_policy=context_only`. Sections present: `trusted_updates` (operator-accepted
decision), `candidate_updates` (candidate decision + built draft/pack/projection — no review overlay →
conservative candidate), `open_loops` (status open/candidate only), `review_needed`. The rejected decision
appears in NEITHER trusted section (→ `excluded_items`). Empty DB → `insufficient_context` with empty
sections. Candidate content raises a data-quality caveat and `requires_operator_review=True`.

## meeting_prep
`status=routed`. Sections: `meeting_objective` (echoes objective/meeting_title/attendee counts),
`trusted_context` (operator-selected explicit artifacts + operator-accepted decisions), `candidate_context`,
`prior_decisions`, `known_preferences`, `open_loops`, `questions_to_resolve`. A supplied-but-missing
`draft_id` → `missing_draft` warning + a "could not be found" question, NOT a build. An explicit draft with
zero citations → `draft_has_no_citations` + `missing_citation_coverage`.

## project_intelligence_context
`status=routed`. Sections: `project_scope` (echoes project_key/domain/query/source_root_key), `trusted_facts`
(operator-accepted claim, as a REFERENCE — no `claim_text`/`evidence_excerpt`), `candidate_findings`
(unreviewed claim), `source_files` (INDEXED metadata only — empty when no index, never a live read/snippet),
`decisions_preferences`, `open_loops`, `review_needed`. Claim bodies (`SECRET CLAIM BODY` /
`SECRET EVIDENCE EXCERPT`) never appear in the envelope.

## open_loop_triage
`status=routed`. Buckets: `active_open_loops` (status open, non-waiting), `blocked_or_waiting`
(open_loop_type waiting_for), `candidate_open_loops` (status candidate), `stale_or_superseded` (stale/
superseded/rejected — and NOT also flagged review-needed), `review_needed` (active/candidate loops whose
review_state is unreviewed/needs_review), `related_decisions`. A `closed` loop is surfaced nowhere. An
explicit missing `open_loop_id` → `missing_required_artifact` (never built); an explicit present id →
routed with the loop in its bucket.
