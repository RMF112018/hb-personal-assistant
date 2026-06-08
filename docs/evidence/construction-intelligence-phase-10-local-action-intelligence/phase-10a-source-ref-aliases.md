# Phase 10A — Source-ref aliases (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Required changes — results

| # | Change | Result |
| --- | --- | --- |
| 1 | Deterministic `src_N` aliases over known refs (packet first) | PASS |
| 2 | Model output contract: source_refs are aliases; prompt `allowed_source_aliases` block + rules | PASS |
| 3 | Resolve aliases → canonical refs before validation/persistence; source_family authoritative | PASS |
| 4 | Reject unresolved (`<excerpt1>`/`src_999`/labels) → `source_alias_not_in_packet`, no persist, no guessing | PASS |
| 5 | Backward compat: canonical raw refs + raw-array + object-root still work | PASS |
| 6 | Prompt example uses aliases only (`src_1`) + warning; placeholder `<ref-from-excerpt>` removed | PASS |
| 7 | Diagnostics: source_alias_count / candidate_refs_resolved_count / candidate_refs_unresolved_count / unresolved_ref_reason (no raw content) | PASS |
| 8 | Tests added (alias→family, mixed, reject, back-compat, dry-run/apply, prompt) | PASS |
| 9 | CLI extract-packet unchanged; `src_1` no longer rejected as source_ref_not_in_packet | PASS |

## Alias → outcome matrix (verified, mock)

| Model `source_refs` | accepted | persisted | persisted source_family |
| --- | --- | --- | --- |
| `["src_1"]` thread packet | 1 | 1 (apply) | `email_thread_raw_context` (canonical `t1`) |
| `["src_1"]` calendar packet | 1 | 1 | `calendar_event_raw_content` (canonical `e1`) |
| `["src_2","src_3"]` related | 1 | 1 | `email_message_raw_content` + `calendar_event_raw_content` |
| `["<excerpt1>"]` | 0 | 0 | rejected `source_alias_not_in_packet` |
| `["src_999"]` | 0 | 0 | rejected `source_alias_not_in_packet` |
| `["m1"]` canonical | 1 | 1 | resolves to self (backward compat) |
| `["src_1"]` dry-run | 1 | 0 | zero writes |

## Acceptance criteria

- Live dry-run no longer rejects a good candidate solely because the model used `src_1`. ✓
- `src_1` resolves to the canonical source ref before persistence. ✓
- `candidate_source_refs.source_family` correct for thread/message/calendar refs. ✓
- `<excerpt1>` rejected with a clear source-alias error. ✓
- Existing canonical-ref mock tests remain green; all targeted Phase 10A packet/extraction tests pass. ✓
- MCP no-raw and no-writeback proofs remain green. ✓

## Diagnostics safety

The `diagnostics` block carries counts, booleans, type names, the diagnostic `reason`, and aliases
(`src_N`) only — no raw email body, subject, URL, token, or full raw source content. Canonical refs
appear only in persisted `candidate_source_refs.source_ref_hash` (unchanged).

## Validation

```
compileall src tests …………………………………… OK
ruff (raw_action_intelligence + tests) ……… clean
mypy (raw_action_intelligence) ……………………… Success
pytest 128 — packet_extraction_safety (alias resolution/family/mixed/reject/back-compat/dry-run/apply +
  prompt test) + raw_action_intelligence + raw_extraction_hardening + raw_model_context_packets +
  packet_scope + relationship_scoring + packet_budget + packet_normalization + phase_10_schema +
  phase_08d_no_raw_access + phase_08d_no_writeback + second_brain_no_writeback_proof +
  local_model_readiness + phase_10_contracts … all pass
```

## Next recommended validation (no apply)

```bash
hb-assistant second-brain phase-10 extract-packet --thread-ref "$THREAD_REF" --dry-run --db "$DB" \
  --timeout-seconds 180 --json
# expect: accepted candidate(s) (src_1 resolved) | no_candidates | explicit schema/business or
# unresolved-alias rejection — NOT source_ref_not_in_packet for a model citing src_1.
```
