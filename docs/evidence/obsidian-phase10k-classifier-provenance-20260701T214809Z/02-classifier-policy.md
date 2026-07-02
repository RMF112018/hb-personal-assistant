# Phase 10K — Classifier repair policy (deterministic, explainable)

Implemented in `src/hb_assistant/obsidian_mcp/source_document_classifier.py` (pure, dependency-light).

## Output (SourceDocumentClassification)
`document_type, confidence (high|medium|low), classification_reason (PM-safe), classification_signals
(deterministic tokens only — never raw paths/excerpt), classification_conflict, conflict_reason,
review_required`.

## Repairable families (guarded — three only)
| family signal (`_title_signal`) | → document_type | hard-conflict types repaired |
|---|---|---|
| value_analysis_log | `value_analysis` | warranty, contract, submittal |
| specification_generic | `specification_template` | submittal, scope_of_work, warranty, contract |
| memo_questions | `clarification_memo` | scope_of_work, contract, submittal, warranty |

A repair also refines a *weak/ambiguous* base type (general_pdf/general_document/reference_document/
template_form/spreadsheet/cost_document/specification/unknown) at **medium** confidence. Any other
confident, unrelated type is NEVER overwritten.

## Signal precedence (strong multi-signal required — amendment 5)
1. Strong title/filename signal AND strong extracted-text evidence (VA, spec-template).
2. Genuine excerpt question/open-item structure (clarification memo — filename alone never suffices).
3. Path is deliberately NOT authoritative (a `Submittals/` path never overrides generic-spec text
   structure; a scope folder never overrides question structure).
4. Existing classifier label is a hint, not ground truth.
5. Thin/ambiguous → keep existing type, `review_required=True` (no guess).

## Discriminators proven by tests
- A real submittal for section `02 87 13` (no specifier/template structure) stays `submittal`.
- A true warranty / scope / contract with no family structure is unchanged.
- `from_detail` regression battery: drawing/warranty/submittal/meeting/contract/schedule/template/email
  classify byte-identically before and after the guarded wire-in.

## Upstream wire-in
`from_detail` gains one guarded final step (`repair_document_type`) after the existing override block —
corrects only the three families under the guard, a no-op otherwise, safe with empty/`text_vault_ref`
excerpts. Classifier document_type conflicts are surfaced/counted; the classifier is not otherwise
rewritten.
