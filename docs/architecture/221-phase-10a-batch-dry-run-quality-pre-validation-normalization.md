# 221. Phase 10A — Batch dry-run quality (pre-validation normalization)

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

Follow-up to ADR 220. The v1.2.7 hardening forced `recommended_next_action="review"` and traceability
defaults via a `model_copy` that runs AFTER `ActionCandidate.model_validate`. But `_high_stakes_routing`
is a `@model_validator(mode="after")` that rejects any high-stakes candidate (`safety_category` ≠
`normal`) whose `recommended_next_action != "review"` — so a high-stakes item the model marked
`accept`/`prepare_packet` was thrown out at validation, before post-validate normalization could save
it. Separately, the model sometimes mislabels a direct ask to Bobby as `assignee=other` /
`waiting_on_others`, which `_validate_business_contract` then rejects as inconsistent. Both depressed the
accepted count on a batch dry-run without improving safety. This moves the `review` normalization (plus
a direct-user-ask correction) to BEFORE validation, and strengthens the prompt. All changes are in
`construction/second_brain/local_ai/raw_action_intelligence.py` + tests (no schema/migration/contract).

## Decision

### Pre-validation normalization — `_normalize_live_item(item)`
Applied to each raw model candidate dict before `ActionCandidate.model_validate` (dict-merge only, no
`.update()`):
- Force `recommended_next_action="review"` — `review` is always valid and satisfies
  `_high_stakes_routing`, so high-stakes `accept`/`prepare_packet` is no longer rejected solely for the
  suggested action. Invalid categories, malformed fields, and unsafe values still fail `model_validate`
  (rejected `schema_or_business_validation_error`), preserving safety.
- Correct a direct Bobby ask (`_DIRECT_USER_ASK_RE` matches "asked/asks/ask Bobby", "@Bobby", "Bobby is
  asked" in title+reason) to `assignee=user` / `waiting_state=waiting_on_me`, UNLESS the title is a
  "Follow up with …" delegation (`_is_followup_title`), which legitimately stays
  `user`/`waiting_on_others`. The regex matches Bobby as the *object* of the ask, not "Bobby asks
  Andrew …" (Bobby delegating).

`_validate_business_contract` now reuses `_is_followup_title` so the correction and the downstream
assignee/waiting consistency check share one follow-up definition. The post-validate `model_copy`
(review + traceability defaults + resolved source_refs) is retained as the persistence guarantee;
forcing `review` twice is harmless.

### Prompt — `STRICT_ACTION_SYSTEM`
Added: direct-ask rule (asked Bobby / @Bobby / Bobby is asked → assignee=user, waiting_on_me); and
evidence-sensitive classification (open questions → `candidate_type=question`, `review`; do not convert
ambiguous risk/status lines into tasks unless the user is clearly asked to act).

## Verified (mock, dry-run)

- High-stakes `schedule`+`accept` and `financial`+`prepare_packet` → accepted, normalized to `review`.
- "Antonio asked Bobby to send draft certification" (model `other`/`waiting_on_others`) → corrected to
  `user`/`waiting_on_me`, accepted. "Rob asked Bobby to resend financial statement" (`financial`,
  model `accept`) → `user`/`waiting_on_me` + `review`, accepted.
- "Follow up with Antonio…" stays `user`/`waiting_on_others`, accepted (exception preserved).
- Invented `src_3` over a single-source thread → rejected `source_alias_not_in_packet`.
- Non-Bobby assignee/waiting inconsistencies still rejected `assignee_waiting_state_inconsistent`.

## Guardrails / non-goals

Dry-run default; no live `--apply`; no email/calendar/Procore/MCP-raw/cloud-LLM writeback. 100% of
accepted candidates remain `recommended_next_action=review`. Source aliases, object-root envelope, and
no-raw/no-writeback proofs preserved. No schema/migration/contract change, no README/ledger bump.
