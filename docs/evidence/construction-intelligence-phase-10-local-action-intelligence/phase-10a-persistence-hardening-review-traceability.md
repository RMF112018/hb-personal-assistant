# Phase 10A — Persistence hardening: force review + traceability (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Required changes — results

| # | Change | Result |
| --- | --- | --- |
| 1 | Force `recommended_next_action="review"` for all live local-model candidates before persistence | PASS — accept-loop `model_copy` in `raw_action_intelligence.py` |
| 2 | Populate traceability defaults when the model omits them | PASS — `model_profile_id=default_extract`, `prompt_template_version=phase10a-action-extraction-v1.2.7`, `model_name` (client/mock), `input_window_hash` (sha256(prompt)[:12]) |
| 3 | Tests: accept→persisted-as-review; non-null `model_profile_id`/`prompt_template_version`; guard columns 0 | PASS — `test_phase_10a_packet_extraction_safety.py` |
| 4 | Preserve dry-run default, source aliases, object-root envelope, MCP no-raw, no-writeback proofs | PASS |

## Persistence normalization (accept loop)

Every accepted candidate is normalized in one `model_copy` BEFORE report/persist:
`recommended_next_action="review"`; `model_profile_id = model or default_extract`;
`prompt_template_version = model or phase10a-action-extraction-v1.2.7`;
`model_name = model or client.model or "mock"`; `input_window_hash = model or sha256(prompt)[:12]`.
`task_candidates`/`commitment_candidates` carry `model_profile_id`+`prompt_template_version` columns
(persisted); `model_name`/`input_window_hash` have no columns → reporting-only on the candidate dump.

## Verified (mock, apply path)

| Scenario | Expectation | Result |
| --- | --- | --- |
| object-root `src_1`, model `recommended_next_action=accept`, normal safety | persisted row `review` | accepted, persisted as `review` |
| model omits `model_profile_id`/`prompt_template_version` | persisted `default_extract` / `phase10a-action-extraction-v1.2.7` | non-null defaults |
| report candidate | non-null `model_name` (`mock`) + `input_window_hash` | present |
| guard columns | sum 0 on `task_candidates` + `candidate_source_refs` | 0 |

## Validation

```
compileall (raw_action_intelligence + tests) …… OK
ruff (raw_action_intelligence + tests) ………………… clean
mypy (raw_action_intelligence) ……………………………………… Success
pytest — packet_extraction_safety (new: accept→review, traceability defaults, guard 0) +
  raw_action_intelligence + raw_extraction_hardening + raw_model_context_packets + packet_scope +
  relationship_scoring + packet_budget + packet_normalization + phase_10_schema +
  phase_08d_no_raw_access + phase_08d_no_writeback + second_brain_no_writeback_proof +
  local_model_readiness + phase_10_contracts … all pass
```

## Next recommended validation (no apply)

```bash
hb-assistant second-brain phase-10 extract-packet --thread-ref "$THREAD_REF" --dry-run --db "$DB" \
  --timeout-seconds 180 --json
# expect: accepted candidates report recommended_next_action=review with non-null model_profile_id /
# prompt_template_version. Consider --apply on a single thread only once dry-runs show coherent,
# review-gated, traceable candidates.
```
