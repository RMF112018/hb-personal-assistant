# 07 — Budget & Truncation

`DraftBudget` (clamped hard caps): `max_sections` (≤500), `max_chars` (≤200k), `max_chars_per_section`
(≤8k), `max_citations` (≤2000), `max_citations_per_section` (≤25), `max_trusted_sections`,
`max_candidate_sections`, `max_open_questions`, and include flags (candidates/deferred/stale/
excluded_manifest/evidence/metadata). `.for_type()`: `trusted_answer_draft` → include_candidates=False;
`implementation_context_draft` → include_stale=False.

- Section budget caps by count, per-kind (trusted/candidate/open-question), and total chars; over-budget
  sections are dropped and `truncated` is set + `dropped_count` recorded on the receipt.
- `excluded_manifest` sections are content-minimized (no `section_body`), bounding a huge packet.
- Proof: `test_answer_draft_builder.py::test_budget_caps_sections` (max_sections=2 →
  `truncated is True`, ≤2 sections).
