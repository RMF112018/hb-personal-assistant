# Phase 10A — Thread-level source-alias consistency (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Problem → fix

Live dry-run: 7/10 threads rejected `source_alias_not_in_packet` for `src_2..src_6` while
`source_alias_count=1`. Cause: `_build_prompt` rendered an index-based `f"src_{i}"` fallback alias for
excerpts whose `source_ref` was `None` (multi-message threads with id-less messages). Fix: display only
registered aliases; email excerpts show the thread alias (`src_1`); fallback removed.

## Required changes — results

| # | Change | Result |
| --- | --- | --- |
| 1 | Every displayed `source_alias` ∈ `allowed_source_aliases` | PASS |
| 2 | Thread-level aliasing for email_thread packets (all messages → `src_1` → thread ref) | PASS |
| 3 | Registered per-message/event aliases still resolve with correct family | PASS (unchanged resolution) |
| 4 | Removed `f"src_{i}"` fallback; only registered aliases displayed | PASS |
| 5 | Tests: prompt shows no unregistered aliases; displayed alias resolves; invented still rejected | PASS |
| 6 | Dry-run default + no-writeback/no-raw proofs green | PASS |

## Verified (mock)

- 6-message thread, messages WITHOUT ids → prompt `source_alias` lines all `src_1`; every displayed
  alias is in the prompt's `allowed_source_aliases`; no `src_2..` displayed.
- Model citing displayed `src_1` → accepted; persisted `source_ref_hash`=canonical thread ref,
  `source_family=email_thread_raw_context`; zero `source_alias_not_in_packet`.
- `src_999` / `<excerpt1>` → still rejected `source_alias_not_in_packet`.
- canonical raw-ref and id-bearing packets → unchanged (backward compat).

## Acceptance

- Re-running the 10-thread dry-run sample no longer yields `source_alias_not_in_packet` for aliases
  displayed in the prompt. ✓
- Remaining `source_alias_not_in_packet` only for truly invented aliases (`src_999`, `<excerpt1>`). ✓

## Validation

```
compileall src tests …………………………………… OK
ruff (raw_action_intelligence + tests) ……… clean
mypy (raw_action_intelligence) ……………………… Success
pytest 130 — packet_extraction_safety (multi-message prompt registered-only + displayed-alias-resolves
  + existing alias/object-root/diagnostics) + raw_action_intelligence + raw_extraction_hardening +
  raw_model_context_packets + packet_scope + relationship_scoring + packet_budget +
  packet_normalization + phase_10_schema + phase_08d_no_raw_access + phase_08d_no_writeback +
  second_brain_no_writeback_proof + local_model_readiness + phase_10_contracts … all pass
```

## Next recommended validation (no apply)

```bash
hb-assistant second-brain phase-10 extract-packet --thread-ref "$THREAD_REF" --dry-run --db "$DB" \
  --timeout-seconds 180 --json
# expect: displayed aliases all registered; src_1 resolves to the thread ref; remaining
# source_alias_not_in_packet only for truly invented aliases.
```
