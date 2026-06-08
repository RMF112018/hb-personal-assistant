# 219. Phase 10A — Assignee / waiting_state candidate quality

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

Follow-up to ADR 218. Live dry-run produces alias-resolvable candidates, but the model sometimes
mislabels `assignee`/`waiting_state` (user-assigned yet `waiting_on_others`, or `not_applicable` on a
real task). This adds explicit prompt rules and deterministic post-validation consistency checks so
incoherent task/commitment candidates are rejected before any apply. All changes are in
`construction/second_brain/local_ai/raw_action_intelligence.py` + tests (no schema/migration/contract).

## Decision

### Prompt rules — `STRICT_ACTION_SYSTEM`
Explicit assignee/waiting_state guidance: user-asked → `assignee=user`/`waiting_state=waiting_on_me`;
user asks another / another states they will do → `assignee=other`/`waiting_state=waiting_on_others`;
do not use `not_applicable` for tasks; purely informational items emit `{"candidates":[]}`.

### Post-validation consistency — `_validate_business_contract` (task & commitment)
- `assignee=user` + `waiting_state=waiting_on_others` (not a "follow up…" title) → reject
  `assignee_waiting_state_inconsistent`.
- `assignee=other` + `waiting_state=waiting_on_me` (not a "follow up…" title) → reject
  `assignee_waiting_state_inconsistent`.
- `candidate_type=="task"` + `waiting_state=="not_applicable"` → reject
  `task_waiting_state_not_applicable` (non-task types exempt).
- High-stakes → `recommended_next_action=review` is ALREADY enforced upstream by the `ActionCandidate`
  model validator (`_high_stakes_routing`); a high-stakes non-review candidate fails `model_validate`
  and is rejected `schema_or_business_validation_error`. No duplicate check; covered by a test.

## Verified (mock)

- Peter→Bobby (`user`/`waiting_on_me`), Bobby→Andrew (`other`/`waiting_on_others`), Ryan→Bobby
  (`user`/`waiting_on_me`) → accepted.
- `user`+`waiting_on_others` and `other`+`waiting_on_me` (non-followup) → rejected
  `assignee_waiting_state_inconsistent`; same combo with a "Follow up with…" title → accepted.
- task + `not_applicable` → rejected `task_waiting_state_not_applicable`.
- high-stakes `schedule`/`financial` + non-review action → rejected; with review → accepted.

## Guardrails / non-goals

Dry-run default; no live `--apply`; no email/calendar/Procore/MCP-raw/cloud-LLM writeback. Source-alias
behavior, object-root envelope, and no-raw/no-writeback proofs preserved. No schema/migration/contract
change, no README/ledger bump.
