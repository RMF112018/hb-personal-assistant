# Phase 10J — Summary-Quality Hardening — Live Proof (safe / count-only)

Targeted re-summarization of the three previously-misframed source-card families through the hardened
source-grounded, classification-aware five-section path (`build_source_card_summary_prompt` +
`SOURCE_CARD_SUMMARY_SYSTEM_PROMPT` + `validate_summary_quality`). Backend `:8000` stopped for the
apply and faithfully restarted afterward. No card bodies, summary text, source excerpts, titles,
paths, figures, or names appear in this bundle — before/after review text is retained only under the
git-ignored `apply/local-sensitive/` tree.

## Selection (targeted by explicit --summaries-note-rel; --allow-resummarize)
- families_targeted: 3
- cards_attempted: 3
- cards_eligible (full project-scoped pool): 103
- selection_truncated: false

## Apply outcome
- summaries_generated: 3
- summaries_rejected: 0
- cards_written: 3
- cards_left_pending: 0
- classifier_conflicts_surfaced: 3   (document_type surfaced/counted, NOT repaired)
- ollama_calls: 3
- reject_reasons: {} (all three passed the strict quality gate on the first attempt; no gate weakened)

## Invariants (whole apply)
- db_mutations: 0
- queue_delta: 0
- created: 0
- deleted: 0

## Family-level quality assertions (verified by re-reading the three cards; booleans only)
- value_analysis_log__identified_not_warranty: true
- value_analysis_log__line_items_and_statuses_present: true
- value_analysis_log__ref_data_quality_flagged: true
- value_analysis_log__classifier_mismatch_noted_in_limits: true
- generic_spec__section_02_87_13_present: true
- generic_spec__qualified_as_generic_template_not_project_submittal: true
- generic_spec__remediation_actions_and_products_extracted: true
- generic_spec__classifier_mismatch_noted_in_limits: true
- memo_questions__identified_as_clarification_memo_not_scope: true
- memo_questions__question_themes_preserved: true
- memo_questions__classifier_mismatch_noted_in_limits: true

## Follow-up recommended (out of scope here)
- A separate classifier-repair phase should correct the upstream `document_type` for these families
  (this pass surfaces and counts the conflicts but does not mutate the classifier).
