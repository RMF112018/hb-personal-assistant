# Phase 10A — Object-root model output envelope (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Required changes — results

| # | Change | Result |
| --- | --- | --- |
| 1 | Output contract → object-root `{"candidates":[...]}`, array back-compat | PASS — object-root accepted; raw array still accepted |
| 2 | STRICT_ACTION_SYSTEM object-root (`{"candidates":[]}` for none) | PASS |
| 3 | `_build_prompt` object-root + enum example | PASS |
| 4 | Parsing diagnostics: candidates/items list used; missing keys → invalid_output_envelope (not empty); fields root_type/has_candidates_key/has_items_key/response_char_count/parsed_candidate_count; no raw content | PASS |
| 5 | Repair prompt object-root wording | PASS |
| 6 | Tests (object accept/empty, array back-compat, invalid envelope, empty, json, schema-rejected) | PASS |
| 7 | CLI smoke path no longer empty_model_output for object-root | PASS (library/mock object-root accepted; CLI `--no-client`/live-attempt tests retained) |

## Envelope → reason matrix (verified)

| Mock model output | produced | accepted | diagnostics.reason | root_type |
| --- | --- | --- | --- | --- |
| `{"candidates":[<valid>]}` | 1 | 1 | (success) | object |
| `{"candidates":[]}` | 0 | 0 | `no_candidates` | object |
| `[<valid>]` | 1 | 1 | (success) | array |
| `[]` | 0 | 0 | `no_candidates` | array |
| `{}` | 0 | 0 | `invalid_output_envelope` | object |
| `""` | 0 | 0 | `empty_model_output` | (none) |
| `{not json` | 0 | 0 | `invalid_json_output` | (none) |
| generic candidate | 1 | 0 | `schema_rejected_output` | object |

## Acceptance criteria

- Direct mock `{"candidates":[...]}` accepted. ✓
- Direct mock `[]` still accepted (→ `no_candidates`, 0 candidates). ✓
- Live object-root output no longer classified as `empty_model_output`. ✓
- `{}` → `invalid_output_envelope`, not `empty_model_output`. ✓
- No apply-path live persistence enabled/recommended until a live dry-run returns accepted candidates
  or explicit schema/business rejections. ✓

## Diagnostics safety

`diagnostics` carries `model_name`, `profile_id`, `prompt_char_count`, `packet_char_estimate`,
`endpoint_reachable`, `error_class_redacted`, `reason`, `root_type`, `has_candidates_key`,
`has_items_key`, `response_char_count`, `parsed_candidate_count` — counts/booleans/type names only; no
raw response body, prompt text, URL, token, email body/subject, or source content.

## Validation

```
compileall src tests …………………………………… OK
ruff (raw_action_intelligence + tests) ……… clean
mypy (raw_action_intelligence) ……………………… Success
pytest 121 — packet_extraction_safety (object-root/back-compat/envelope/empty/json/schema-rejected),
  raw_action_intelligence, raw_extraction_hardening, raw_model_context_packets, packet_scope,
  relationship_scoring, packet_budget, packet_normalization, phase_10_schema, phase_08d_no_raw_access,
  phase_08d_no_writeback, second_brain_no_writeback_proof, phase_10_local_model_readiness,
  phase_10_contracts … all pass
```

MCP no-raw / no-writeback and Phase 10 schema-status remain green.
