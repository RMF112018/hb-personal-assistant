# Phase 10A — Batch dry-run quality: pre-validation normalization (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Required changes — results

| # | Change | Result |
| --- | --- | --- |
| 1 | Normalize `recommended_next_action="review"` BEFORE `ActionCandidate.model_validate` | PASS — `_normalize_live_item`, called in the accept loop before `model_validate` |
| 1 | Preserve rejection for invalid categories / malformed / unsafe fields | PASS — only `recommended_next_action` (+ direct-ask assignee/waiting) is touched; everything else still hits `model_validate` → `schema_or_business_validation_error` |
| 1 | Keep all persisted live candidates review-gated | PASS — pre-validate review + retained post-validate `model_copy` |
| 2 | Direct Bobby ask → assignee=user, waiting_state=waiting_on_me (correct before validation) | PASS — `_DIRECT_USER_ASK_RE` correction |
| 2 | Exception: "Follow up with [person]…" stays user/waiting_on_others | PASS — `_is_followup_title` suppresses correction |
| 3 | Evidence-sensitive classification (questions → question/review; don't force tasks) | PASS — `STRICT_ACTION_SYSTEM` prompt rules |
| 4 | Sample tests (Antonio, Rob, high-stakes accept→review, invented src_3 rejected) | PASS |

## Behavior (mock, dry-run)

| Scenario | Expectation | Result |
| --- | --- | --- |
| high-stakes `schedule` + model `accept` | normalized → review, accepted | accepted, `review` |
| high-stakes `financial` + model `prepare_packet` | normalized → review, accepted | accepted, `review` |
| "Antonio asked Bobby…" model `other`/`waiting_on_others` | corrected `user`/`waiting_on_me`, accepted | corrected, accepted |
| "Rob asked Bobby…" `financial` + `accept` | `user`/`waiting_on_me` + `review`, accepted | as expected |
| "Follow up with Antonio…" `user`/`waiting_on_others` | unchanged, accepted (exception) | unchanged |
| invented `src_3` over single-source thread | rejected `source_alias_not_in_packet` | rejected |
| non-Bobby `user`+`waiting_on_others` / `other`+`waiting_on_me` | rejected `assignee_waiting_state_inconsistent` | rejected |

## Acceptance mapping

- high-stakes `accept`/`prepare_packet` no longer rejected solely for `recommended_next_action`.
- direct Bobby asks do not persist as `other`/`waiting_on_others`.
- 100% of accepted candidates remain `recommended_next_action=review`.
- accepted count increases (high-stakes accept/prepare_packet + corrected Bobby asks now pass).

## Validation

```
compileall (raw_action_intelligence + tests) …… OK
ruff (raw_action_intelligence + tests) ………………… clean
mypy (raw_action_intelligence) ……………………………………… Success
pytest — packet_extraction_safety (repurposed high-stakes→review, direct-ask correction, follow-up
  exception, invented src_3 rejected) + raw_action_intelligence + raw_extraction_hardening +
  raw_model_context_packets + packet_scope + relationship_scoring + packet_budget +
  packet_normalization + phase_10_schema + phase_08d_no_raw_access + phase_08d_no_writeback +
  second_brain_no_writeback_proof + local_model_readiness + phase_10_contracts … all pass
```

## Next recommended validation (no apply)

```bash
# Re-run the 50-thread dry-run (no --apply). Expect: accepted count >= prior; high-stakes items
# carry recommended_next_action=review; direct Bobby asks read user/waiting_on_me.
hb-assistant second-brain phase-10 extract-packet --thread-ref "$THREAD_REF" --dry-run --db "$DB" \
  --timeout-seconds 180 --json
```
