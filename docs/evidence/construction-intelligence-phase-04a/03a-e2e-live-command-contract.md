# Phase 04A Prompt 03A: E2E Live Command Contract Retrofit

Package file was mislabeled as Prompt 00; this evidence records it as Prompt 03A.

Date: 2026-05-28

## Baseline

- `git rev-parse HEAD` -> `b12f7587000e014db32af98610f2541eacd270e6`
- `git branch --show-current` -> `main`
- `git merge-base --is-ancestor 3b33efee9b34c547851a5e29f4d45c7416df35d2 HEAD; echo $?` -> `0`

## Command Contract Implemented

- Added explicit command-contract endpoint inventory:
  - `hb-assistant procore live endpoints list --json`
- Kept explicit one-command execution surface:
  - `hb-assistant procore live sync --project <key> --endpoint <alias> --apply --sqlite-only --max-pages N --max-items N --confirm-live-get --json`
- Added alias-to-contract mapping in CLI receipts:
  - example: `command_endpoint: "rfis"` + `endpoint_id: "list-rfis"`
- Added deterministic state and reason-code surfaces:
  - `operational`
  - `not_live_verified`
  - `fail_closed_unsupported`

## Required Validation Gates (real outputs)

1. `python -m pytest -q --no-header`
   - Result: pass.
2. `ruff check .`
   - Result: pass (`All checks passed!`).
3. `mypy .`
   - Result: pass (`Success: no issues found in 166 source files`; informational notes only).
4. `python -m compileall src tests`
   - Result: pass.
5. `hb-assistant procore live endpoints list --json`
   - Result: pass (exit `0`) with explicit per-endpoint state + reason codes.

Additional operator checks:

- `hb-assistant procore live sync --help`
  - Result: pass; includes final operator command template with `--confirm-live-get`, `--sqlite-only`, `--max-pages`, and `--max-items`.
- `hb-assistant procore validate --json`
  - Exit `1` expected due existing repo state (`mapping_consistent=false`, store-readiness checks false).
- `hb-assistant procore mapping validate --json`
  - Exit `1` expected due pending mappings (`hilltop`, `hilltop-gardens`).

## Endpoint State Snapshot (contract-driven)

Representative rows from `live endpoints list` output:

- `list-rfis` (`command_endpoint: rfis`) -> `operational` (adapter + normalizer + SQLite path present, verified/live-eligible).
- `list-observations` (`command_endpoint: observations`) -> `not_live_verified` (`reason_codes: ["not_live_verified"]`).
- `list-correspondence` -> `fail_closed_unsupported` (`reason_codes: ["excluded_by_guardrail"]`).
- `list-schedule` / `list-tasks` -> `fail_closed_unsupported` (`reason_codes: ["deferred_by_guardrail"]`).
- multiple verified-but-unadapted families (projects/drawings/punch-items/change-events/commitments/prime-contracts/invoices) -> `fail_closed_unsupported` with:
  - `adapter_missing`
  - `normalizer_missing`
  - `sqlite_upsert_missing`

## Fail-Closed Receipt Shape Proof

`live sync` fail-closed receipt now always includes stable counters and contract fields, for example:

- `oauth_status`
- `command_endpoint`
- `endpoint_id`
- `state`
- `reason_codes`
- `request_count: 0`
- `retrieved_count: 0`
- `normalized_count: 0`
- `sqlite_upsert_count: 0`
- `sqlite_total_count: 0`
- `evidence_path`
- `no_live_call_performed: true`

## No-Live-Call Attestation

- Prompt 03A performs no live Procore API call.
- The regression test `test_prompt_03a_live_sync_contract_never_invokes_transport` asserts live sync contract mode never invokes transport even when live flags are provided.

## Redaction / Secret Safety Attestation

- No access token, refresh token, Authorization value, client secret, raw OAuth payload, or raw Procore response body is persisted in this evidence.
