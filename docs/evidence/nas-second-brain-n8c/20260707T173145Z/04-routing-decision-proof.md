# 04 — Routing-decision proof (deterministic intent)

Precedence (deterministic, no LLM): (1) explicit valid `workflow_type` wins; (2) explicit artifact ids
steer target selection; (3) conservative single-category keyword fallback; (4) ambiguous/empty →
`unknown` → `needs_clarification` (explicit invalid type) or `insufficient_context` (no type at all).

Test-backed:
- `test_explicit_type_wins_over_keyword` — explicit `meeting_prep` beats a `source_file_lookup` query.
- `test_invalid_workflow_type_needs_clarification` — `bogus` → unknown + needs_clarification + warning.
- `test_ambiguous_query_insufficient_context` — "draft meeting invoice" (2 categories) → unknown.
- `test_keyword_fallback_source_lookup` — single-category "contract pdf" → source_file_lookup.
- `classify_workflow_type_from_keywords` returns a type only when EXACTLY one category matches.
