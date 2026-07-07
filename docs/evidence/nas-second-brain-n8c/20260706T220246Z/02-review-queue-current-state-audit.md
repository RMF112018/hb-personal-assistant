# 02 — Review-queue current-state audit (before N8C-9)

Before N8C-9 there was no unified way to ask, across the advisory surfaces, "what needs review / what was
accepted, rejected, deferred, or marked not required / what is stale or superseded". Each surface exposed
its own candidate/status fields but there was no overlay aggregating them or a durable operator
disposition ledger.

Advisory surfaces N8C-9 draws from (read-only):
- N8C-4 `assistant_claims` — candidate/unreviewed claims, decision/task/commitment/risk candidates,
  low-confidence, stale source_state.
- N8C-5 `assistant_enrichment_receipts` → derived `enrichment_review` items (needs_operator_review /
  source_stale / low_confidence / claim_candidate / link_candidate tiers).
- N8C-6 `assistant_context_pack_items` — items with `review_tier != safe_summary`, stale/truncated.
- N8C-7 `assistant_memory_compilations` (+ nodes/mentions) — needs_operator_review / stale / truncated.
- N8C-8 `assistant_decision_records` / `assistant_preference_records` / `assistant_open_loop_records` —
  `status=candidate` / `review_state=unreviewed`.

Gap closed: N8C-9 introduces a durable, source-backed review overlay (queue + append-only disposition
ledger + computed effective-state read model) without mutating any of the above.
