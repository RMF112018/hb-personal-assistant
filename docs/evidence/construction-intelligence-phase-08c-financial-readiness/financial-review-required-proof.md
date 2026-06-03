# Financial Review-Required Routing Proof

Deterministic routing of sensitive/ambiguous financial signals to review. Every item below is an advisory review aid only — not a payment approval, claim position, entitlement determination, contract interpretation, forecast, or executive financial determination. No financial values are computed or summed here.

## Summary
- Run id: 08c-review-31b7b8a8
- Project key: all
- Schema version: 36
- Items evaluated: 1281
- Review items routed: 641

## By trigger category (reason code)
| Trigger category (reason code) | Review tier | Confidence | Count |
| --- | --- | --- | --- |
| missing_wbs_cost_code_or_line_item_type | operator_review | medium | 641 |

## Review tiers in use
- operator_review: 641

## Policy (loaded + enforced)
- Review tiers: none, operator_review, financial_review, executive_review, legal_contract_review
- Triggers: amount_parse_ambiguous_or_rejected, missing_or_inconsistent_currency, missing_wbs_cost_code_or_line_item_type, missing_source_field_path, relationship_ambiguity, fail_closed_required_source, determination_attempt

## Guardrails
- advisory_only_required: true
- no_external_writeback: true
- financial_determination_forbidden: true
- payment_decision_forbidden: true
- claim_or_entitlement_decision_forbidden: true
- raw_financial_payload_forbidden: true

## Stop-check attestations
- raw_payloads_or_full_source_values_written: false
- financial_determination_performed: false
- model_required: false

## Notes
Deterministic routing of the seven review-required financial signal categories from V35 normalized facts + coverage snapshots + procore_financial_* source tables. trigger_category is the reason code; source_ref/amount_ref are metadata references only (no amounts, URLs, tokens, bodies, or payloads). confidence_label is the advisory quality of the routing signal, not certainty of any financial outcome. All outputs are advisory review aids only — not determinations, approvals, claims, entitlements, or forecasts. Source preserved in procore_financial_* tables.

## Artifacts
- docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-review-required-proof.json
- docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-readiness-agent-proof.json
- docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-source-coverage-matrix.json

Generated: 2026-06-03T17:01:14.860777Z | run_id: 08c-review-31b7b8a8
