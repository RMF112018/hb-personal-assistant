# Phase 10A — Live extract-packet + source-family attribution (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Required changes — results

| # | Change | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Source-family from packet source_refs (no string guessing) | PASS | `known_family = {**excerpt_family, **packet_source_refs}`; thread→email_thread_raw_context, message→email_message_raw_content, event→calendar_event_raw_content; `test_thread_ref_citation_persists_email_thread_family`, `test_event_ref_citation_persists_calendar_family` |
| 1 | Unknown ref handling | PASS | candidate citing a ref not in packet/excerpts is rejected (`source_ref_not_in_packet`); `test_unknown_source_ref_is_rejected` |
| 2 | Pass packet source_refs into extraction + validate before persist | PASS | `extract_actions_for_packet` builds `source_family_map`; refs validated in the accept phase |
| 3 | Live model client wiring | PASS | `resolve_local_model_client` → `mistral-nemo:12b` default; CLI `--profile/--model/--provider/--timeout-seconds`; `live_model_client_missing` before extraction when none |
| 3 | No false "model returned no output" | PASS | no-client path returns `note="no_model_client"`, `reason="no_client_constructed"` |
| 4 | Distinct diagnostics | PASS | `no_client_constructed`, `ollama_unreachable`, `model_timeout`, `empty_model_output`, `invalid_json_output`, `schema_rejected_output`; `test_diagnostic_reasons_distinguish_failure_modes` |

## Acceptance criteria

- THREAD_REF mock apply → `candidate_source_refs.source_family == "email_thread_raw_context"`. ✓
- Live single-thread dry-run (no daemon in test env) → `model_name == "mistral-nemo:12b"` with a
  concrete redacted reason (`ollama_unreachable`, code `ollama_request_failed`). ✓
- A live extraction attempt never reports `model_name=null` / `endpoint_reachable=null` unless the
  command explicitly used `--no-client` test mode (→ `no_client_constructed`). ✓

## Diagnostics safety

`diagnostics` carries only `model_name`, `profile_id`, `prompt_char_count`, `packet_char_estimate`,
`endpoint_reachable` (bool/None), `error_class_redacted` (OllamaUnavailable category code or type name),
and `reason`. No raw body/subject/URL/token/join link.

## Validation

```
compileall src tests …………………………………… OK
ruff (changed modules + tests) …………………… clean
mypy (raw_action_intelligence, provider) … Success
pytest 119 — packet_extraction_safety, packet_scope, relationship_scoring, packet_budget,
  packet_normalization, raw_action_intelligence, raw_extraction_hardening, raw_model_context_packets,
  phase_10_schema, phase_08d_no_raw_access, phase_08d_no_writeback, second_brain_no_writeback_proof,
  phase_10_local_model_readiness, phase_10_contracts … all pass
CLI: extract-packet --no-client → no_client_constructed; --timeout-seconds 1 (live) → model_name=mistral-nemo:12b + ollama_unreachable
```

MCP no-raw / no-writeback and Phase 10 schema-status remain green.
