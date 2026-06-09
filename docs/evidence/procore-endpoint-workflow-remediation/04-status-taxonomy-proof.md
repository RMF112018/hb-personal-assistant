# 04 — Endpoint Status Taxonomy & Receipts Proof

Prompt: `04_ENDPOINT_STATUS_TAXONOMY_AND_RECEIPTS.md`. Generic per-endpoint
`error` receipts are replaced with an actionable, operator-safe taxonomy.

## Taxonomy (in `procore/daily_refresh_plan.py`)

`classify_receipt(receipt)` maps a `run_live_sync` receipt to one code:

| code | trigger |
| --- | --- |
| `success` | receipt state `success` (or `partial_success` with no projection error) |
| `skipped_company_level_already_handled` | company-level endpoint already fetched once; remaining pilots |
| `skipped_tool_not_enabled` | no canonical adapter (`list-drawings`), `fail_closed_unsupported`, or HTTP **404** |
| `skipped_permission_limited` | HTTP **403** |
| `skipped_not_live_eligible` | adapter `live_verified=False` (`not_live_verified`) |
| `blocked_auth_not_ready` | gate_blocked w/ `live_env_not_set`/`confirm_live_get_required`/`token_provider_unavailable` |
| `blocked_mapping_not_ready` | gate_blocked w/ mapping/project-id reasons |
| `contract_bug_missing_required_param` | HTTP **400** |
| `transport_rate_limited` | HTTP **429** |
| `transport_error_retryable` | HTTP **5xx** |
| `transport_error_non_retryable` | other transport error |
| `normalizer_missing` | adapter verified but no normalizer registered |
| `projection_error` | `partial_success` with a `*_projection_error` redacted entry |
| `unknown_degraded` | unclassified |

## HTTP classification rules (implemented)

- **400** → `contract_bug_missing_required_param` (caller param defect).
- **403** → `skipped_permission_limited` (no blind retry).
- **404** → `skipped_tool_not_enabled` (tool disabled / unsupported for the pilot; route-template bugs were already fixed by routing through canonical adapters).
- **429** → `transport_rate_limited` (obeys `run_live_sync`'s bounded retry policy).
- **5xx** → `transport_error_retryable`; other → `transport_error_non_retryable`.

HTTP status is extracted safely from `redacted_errors[].status` / `reason_codes`
(`transport_error:<status>`) — **never** from a raw response body.

## Degradation semantics

`is_degraded_status` returns True for `contract_bug_*`, `transport_*`,
`normalizer_missing`, `projection_error`, `blocked_*`, `unknown_degraded`.
Intentional `skipped_*` codes are **not** degradation. So with the canonical
routing, a daily run where the 6 fixable endpoints succeed and `list-drawings`
is `skipped_tool_not_enabled` is **`ok`**, not degraded — while any genuine
contract/transport failure still degrades the run (and a manual run exits 2).

## Receipt contents (operator-safe)

The Procore stage summary (persisted in the full orchestrator summary at
`evidence_summary_path`, and surfaced via scheduler status) now carries:

- `persistence_path: "procore_live"` and `canonical_tables` / `tables_written`.
- `endpoint_summary`: `endpoints_planned`, `endpoints_succeeded`, `endpoints_skipped`, `contract_bug_failures`, `externally_blocked`, and a `by_status` histogram.
- `endpoints[]`: per `{endpoint, legacy_alias, scope (company|project_key), status, retrieved, upserted}`.
- `projects[]`: per-project `{endpoints_ok, endpoints_skipped, endpoints_failed, status}`.
- `next_operator_action` (Procore-specific) + `inspect_hint` (how to inspect canonical data safely).

**Never** included: tokens, auth headers, raw payloads, signed URLs, raw private
response bodies, or complete Procore error bodies. Status codes + redacted
`{code,status}` only. The orchestrator's existing `_REDACT_TOKENS` write-fence
(`redact_json`) and the scheduler receipt redactor remain in force.

## Tests

Classification, receipt-shape, token-scrub, and degraded-exit tests are added in
Phase F (`08-tests-and-guardrails.md`); the degraded-exit behavior is already
covered by `tests/test_scheduler_degraded_surfacing.py` (manual degraded → exit 2).
