# 06 — Context / artifact / policy bounding proof

The four broker-side view helpers are pure SELECTs over the already-bounded router envelope — no extra
repository reads, no logic, no classification.

- context view → workflow_id/type/status + selected_artifacts + citations + source_refs + review_labels +
  open_questions + risks_or_caveats + deferred_capabilities + advisory_next_steps + warnings + policy.
- artifacts view → selected_artifacts (references only) + count + warnings + policy.
- policy view → the five policy fields + request echo.
- summary view → routing_decision + counts + deferred_capabilities + warnings + policy (NON-FINAL).

Tests: `test_context_is_bounded_whitelisted` (no `_json`/`section_body`/`evidence_excerpt`/`result_json`
in the payload), `test_artifacts_are_references_not_payloads` (artifact keys ⊆ a small ref set; metadata
carries no `*_json`), `test_policy_view_is_no_execution`, `test_summary_is_nonfinal_route_metadata`,
`test_inputs_are_clamped` (5000-char query truncated to ≤1000 in the echoed request).
