# 04 — Citation-Safe Drafting Rules (builder)

`answer_draft_builder.py` — deterministic, packet-scoped, no LLM. Consumes the packet header + items
(`included_only=False`) + citations + the parsed `answer_contract`.

1. **Gate (clarification #1/#5):** `answer_contract.answer_allowed is True` is the ONLY gate (defaults False
   when missing/ambiguous — never assumed True). If False → emit **exactly one** `insufficient_support`
   section with bounded reason metadata (counts + unresolved/must_not_say counts), **no fabricated
   direct_answer**, no citations.
2. **trusted_answer_draft:** only `trusted` items become answer-support; candidate/deferred/stale/rejected/
   not_required/superseded → bounded `excluded_manifest` (never support).
3. **review_aware_answer_draft:** trusted → direct_answer/trusted_context; candidate → `candidate_context`
   WITH a visible `review_label` ("candidate — review required"); deferred/stale → open_question/risk **if
   policy**; rejected/not_required/superseded → `excluded_manifest` only.
4. **Every answer-support section is cited (≥1):** direct_answer/trusted_context/candidate_context/
   source_summary/implementation_note carry ≥1 citation; a support section whose packet item had no citation
   manifest gets a citation synthesized from the item's own provenance anchor (lineage marked `degraded`).
   open_question/caveat/risk/excluded_manifest/insufficient_support may omit.
5. **must_not_say honored (clarification #5):** any `must_not_say` target (and every hard-excluded state)
   never appears as support — routed to a bounded, content-minimized `excluded_manifest` (ids/state/reason/
   label only; `section_body` is NULL).
6. **Open loops stay advisory:** `implementation_note` / `open_question` — never tasks/commands/reminders/jobs.
7. **Draft, never final:** output is labelled a DRAFT. **No `final_answer`/`answer_text`/`generated_answer`/
   `operator_approved_answer`/`authoritative_answer` field anywhere.**

**Section body (clarification #4):** a bounded restatement assembled ONLY from the packet item's own
`title` + `summary` + (`evidence_excerpt` when the budget includes evidence) — no inferred facts, no
gap-bridging. `review_label` is derived deterministically from `inclusion_state`/`effective_state`.
