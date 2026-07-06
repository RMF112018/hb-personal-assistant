# N8C-8 — risk & defer list

## Deferred (intentionally out of scope)
- **Operator disposition workflow** (accept / reject / close / reopen). Enum values reserved
  (`accepted`/`rejected`/`open`/`closed`/`operator_*`, `closed`/`reopened` events) but no transition is
  implemented. N8C-8 does creation + explicit stale + lineage-scoped supersede only.
- **Remote write/action tools.** MCP exposes list/get only. No accept/reject/close/reopen/reminder/
  action/extract/apply MCP tool.
- **Action execution of any kind** (email/calendar/task/Slack/notification/reminder). Records are
  advisory; identifying an open loop never acts on it.
- **Rich compilation signal.** N8C-7 compilations currently populate `preferences_json`/`risks_json`/
  `open_questions_json` thinly; the compilation-derived path is exercised via seeded arrays and stays a
  WEAK tier (≤0.4 confidence, `needs_review`). Richer signal awaits a future N8C-7 enrichment.
- **`question` claim_type.** Not added to the V100 taxonomy (V100 untouched); questions are derived as a
  conservative, bounded, low-confidence open-loop heuristic instead.

## Risks & mitigations
- *Cross-source clobber* → mitigated: `anchor_key` is baked into `identity_key`, so independent sources
  coexist; supersede is lineage-scoped (proved by `test_independent_sources_coexist`).
- *Weak signal treated as truth* → mitigated: compilation-derived + question records are the weakest
  tier (`needs_review`, capped confidence, `compilation_derived` metadata).
- *Schema-head test drift* → the N8C-7 `test_memory_v103_migration.py::test_head_is_103` (hard head
  equality) was updated to `test_v103_present_and_head_at_least_103` for the V104 bump — same non-head
  treatment N8C-7 applied to the V102 test. No behavior change; V103 row/tables still asserted.

## Follow-ups a later slice may pick up
Operator review surfaces (accept/reject), open-loop close/reopen with an audit trail, due-date/priority
review, and (only if Bobby directs it) any N8C↔N8D integration — none of which N8C-8 touches.
