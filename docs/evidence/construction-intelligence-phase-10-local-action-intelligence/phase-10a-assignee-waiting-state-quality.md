# Phase 10A — Assignee / waiting_state candidate quality (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Required changes — results

| # | Change | Result |
| --- | --- | --- |
| 1 | Prompt rules for assignee/waiting_state (+ informational → no_candidates) | PASS — added to STRICT_ACTION_SYSTEM |
| 2 | Post-validation consistency checks | PASS — `_validate_business_contract` |
| 2 | high-stakes keeps recommended_next_action=review | PASS — enforced by ActionCandidate model validator (upstream) |
| 3 | Sample-case tests | PASS |
| 4 | Preserve dry-run / no-writeback / alias / object-root / MCP proofs | PASS |

## Consistency rules (task & commitment)

- `assignee=user` + `waiting_state=waiting_on_others` (non follow-up title) → `assignee_waiting_state_inconsistent`.
- `assignee=other` + `waiting_state=waiting_on_me` (non follow-up title) → `assignee_waiting_state_inconsistent`.
- task + `waiting_state=not_applicable` → `task_waiting_state_not_applicable`.
- "Follow up with…" titles are exempt from the assignee/waiting inconsistency rule.
- High-stakes (`safety_category` ≠ normal) with `recommended_next_action != review` → rejected by the
  model validator (`schema_or_business_validation_error`).

## Verified (mock, dry-run)

| Candidate | assignee / waiting_state | result |
| --- | --- | --- |
| Peter asks Bobby to confirm | user / waiting_on_me | accepted |
| Bobby asks Andrew to add | other / waiting_on_others | accepted |
| Ryan asks Bobby to forward | user / waiting_on_me | accepted |
| (inconsistent) | user / waiting_on_others | rejected `assignee_waiting_state_inconsistent` |
| (inconsistent) | other / waiting_on_me | rejected `assignee_waiting_state_inconsistent` |
| "Follow up with Andrew…" | user / waiting_on_others | accepted (exception) |
| task | not_applicable | rejected `task_waiting_state_not_applicable` |
| high-stakes schedule/financial | recommended_next_action=accept | rejected |
| high-stakes financial | recommended_next_action=review | accepted |

## Validation

```
compileall src tests …………………………………… OK
ruff (raw_action_intelligence + tests) ……… clean
mypy (raw_action_intelligence) ……………………… Success
pytest 133 — packet_extraction_safety (new: assignee/waiting quality cases, inconsistencies rejected,
  high-stakes non-review rejected) + raw_action_intelligence (good-mock fixture corrected to a coherent
  waiting_on_me) + raw_extraction_hardening + raw_model_context_packets + packet_scope +
  relationship_scoring + packet_budget + packet_normalization + phase_10_schema +
  phase_08d_no_raw_access + phase_08d_no_writeback + second_brain_no_writeback_proof +
  local_model_readiness + phase_10_contracts … all pass
```

## Next recommended validation (no apply)

```bash
hb-assistant second-brain phase-10 extract-packet --thread-ref "$THREAD_REF" --dry-run --db "$DB" \
  --timeout-seconds 180 --json
# expect: accepted candidates carry coherent assignee/waiting_state; incoherent ones rejected with
# assignee_waiting_state_inconsistent / task_waiting_state_not_applicable.
```
