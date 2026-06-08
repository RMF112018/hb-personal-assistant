# Phase 10A — Related-Packet Tightening + Extraction Diagnostics (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Required changes — results

| # | Change | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Blocked related packet does not call model | PASS | `extract_actions_for_packet` returns `extracted=false, blocked=true, persisted=0` + note/best_confidence; `test_blocked_related_packet_never_calls_model` (mock that would produce a candidate yields nothing) |
| 2 | Related budget enforcement | PASS | lower-confidence counterparts excluded when combined budget overflows; `excluded_item_count`/`truncated` reported; `test_related_packet_budget_excludes_low_confidence` |
| 3 | Scoring precision (anchor gate) | PASS | participant-overlap-only ⇒ weak/`anchor_present=false`; generic term (`proposal`) ⇒ no `shared_record_reference`, weak; specific `RFI 42` ⇒ anchor; `test_phase_10a_relationship_scoring` |
| 3/4 | Combined extraction strong-by-default | PASS | `build_related` default = STRONG; `--allow-moderate` ⇒ moderate review-only; `test_combined_extraction_defaults_to_strong_only` |
| 5 | Per-ref source-family attribution | PASS | candidate citing email+calendar refs ⇒ each `candidate_source_refs.source_family` matches its ref (not all-email); `test_related_packet_per_ref_source_family_attribution` |
| 6 | Live-extraction diagnostics | PASS | no-output run returns redacted `diagnostics` (model_name, profile_id, prompt_char_count, packet_char_estimate, endpoint_reachable, error_class_redacted); `test_no_output_run_returns_safe_diagnostics` |
| CLI | dry-run clarity | PASS | `--dry-run/--apply` pair (default dry-run), `--allow-moderate`, `--mock-output` offline path; `test_cli_extract_packet_dry_run_is_default_and_writes_nothing` |

## Scoring precision (deterministic)

- Specific shared record identifier = record token + number (`RFI 42`); generic terms
  (bid/proposal/meeting/agenda/review/coordination) are weak on their own.
- Anchor gate: confidence capped to 0.40 (weak) unless `same_project`, near-exact subject (Jaccard ≥
  0.6), `time_proximity AND participant_overlap`, or a specific shared record is present.
- Combined extraction defaults to strong (≥0.80); moderate (0.55–<0.80) is review-only via
  `--allow-moderate`; weak (<0.55) never combines.

## Diagnostics safety

`diagnostics` carries type names, char counts, and booleans only — no raw body, subject, URL, token, or
join link. `error_class_redacted` is the exception type name (no message). `endpoint_reachable` is a
bool/None derived from the error class.

## Validation

```
compileall src tests …………………………………… OK
ruff (changed modules + tests) …………………… clean
mypy (relationship_scoring, packet_builders, raw_action_intelligence) … Success
pytest 104 — packet_scope, relationship_scoring, packet_normalization, packet_budget,
  packet_extraction_safety, raw_action_intelligence, raw_extraction_hardening,
  raw_model_context_packets, phase_10_schema, phase_08d_no_raw_access, phase_08d_no_writeback,
  second_brain_no_writeback_proof, phase_10_contracts … all pass
extract-packet --help → "--dry-run --apply [default: dry-run]", --allow-moderate, --mock-output
```

MCP no-raw / no-writeback and Phase 10 schema-status remain green.
