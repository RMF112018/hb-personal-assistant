# Procore Null Projection Patch 1 Evidence

Timestamp: `20260619T064429Z`

## Scope

Patch 1 was limited to source-backed scalar decomposition fields for `commitment-change-orders` and `prime-change-orders`. No registry, projection engine, schema migration, Budget Detail refresh/reconciliation, company_id derivation, live Procore call, scheduler call, SourceRefreshOrchestrator call, broad refresh, or writeback was performed.

## Decision

Repo truth showed the destination scalar columns and registry mappings already exist. The copied-DB reset replay proved the current generic endpoint projection writes the mapped nested scalar fields. Therefore this patch records focused regression coverage and body-free evidence rather than changing projection code or registry JSON.

## Source Paths And Destinations

| Endpoint | Destination column | Source JSON path |
| --- | --- | --- |
| commitment-change-orders | procore_ep_commitment_change_orders.change_order_change_reason_id | $.change_order_change_reason.id |
| commitment-change-orders | procore_ep_commitment_change_orders.change_order_change_reason_change_reason | $.change_order_change_reason.change_reason |
| commitment-change-orders | procore_ep_commitment_change_orders.designated_reviewer_id | $.designated_reviewer.id |
| commitment-change-orders | procore_ep_commitment_change_orders.designated_reviewer_name | $.designated_reviewer.name |
| commitment-change-orders | procore_ep_commitment_change_orders.received_from_id | $.received_from.id |
| commitment-change-orders | procore_ep_commitment_change_orders.received_from_name | $.received_from.name |
| commitment-change-orders | procore_ep_commitment_change_orders.reviewed_by_id | $.reviewed_by.id |
| commitment-change-orders | procore_ep_commitment_change_orders.reviewed_by_name | $.reviewed_by.name |
| prime-change-orders | procore_ep_prime_change_orders.change_order_change_reason_id | $.change_order_change_reason.id |
| prime-change-orders | procore_ep_prime_change_orders.change_order_change_reason_change_reason | $.change_order_change_reason.change_reason |
| prime-change-orders | procore_ep_prime_change_orders.designated_reviewer_id | $.designated_reviewer.id |
| prime-change-orders | procore_ep_prime_change_orders.designated_reviewer_name | $.designated_reviewer.name |
| prime-change-orders | procore_ep_prime_change_orders.received_from_id | $.received_from.id |
| prime-change-orders | procore_ep_prime_change_orders.received_from_name | $.received_from.name |

## Copied-DB Reset Replay Result

`pre-patch-target-column-counts.json` captures the copied-DB baseline. `reset-target-column-counts.json` sets only the Patch 1 target columns to null on the copy. Endpoint-limited copied-DB replay then repopulated the target fields:

| Table | Column | After reset non-null | After replay non-null |
| --- | --- | ---: | ---: |
| procore_ep_commitment_change_orders | change_order_change_reason_id | 0 | 98 |
| procore_ep_commitment_change_orders | change_order_change_reason_change_reason | 0 | 98 |
| procore_ep_commitment_change_orders | designated_reviewer_id | 0 | 68 |
| procore_ep_commitment_change_orders | designated_reviewer_name | 0 | 68 |
| procore_ep_commitment_change_orders | received_from_id | 0 | 21 |
| procore_ep_commitment_change_orders | received_from_name | 0 | 21 |
| procore_ep_commitment_change_orders | reviewed_by_id | 0 | 1 |
| procore_ep_commitment_change_orders | reviewed_by_name | 0 | 1 |
| procore_ep_prime_change_orders | change_order_change_reason_id | 0 | 60 |
| procore_ep_prime_change_orders | change_order_change_reason_change_reason | 0 | 60 |
| procore_ep_prime_change_orders | designated_reviewer_id | 0 | 19 |
| procore_ep_prime_change_orders | designated_reviewer_name | 0 | 19 |
| procore_ep_prime_change_orders | received_from_id | 0 | 36 |
| procore_ep_prime_change_orders | received_from_name | 0 | 36 |

## Guardrails

- Bare object/container columns were not populated by this proof.
- `company_id` remained deferred and was not derived or backfilled.
- Budget Detail rows/cells/columns remained unchanged and nonzero.
- No raw payload bodies, payload fragments, names, emails, notes, descriptions, comments, signed URLs, credentials, or sample values are emitted in this evidence.
- Raw payload values emitted: `false`.

## Validation

- Focused projection regression tests were added for both target endpoints.
- Copied DB `PRAGMA integrity_check` result: `ok`.
- Copied DB `PRAGMA quick_check` result: `ok`.
- Endpoint-limited copied-DB replays wrote only `commitment-change-orders` and `prime-change-orders`.
- `python -m json.tool src/hb_assistant/procore/projection_registry.json`: passed.
- `python -m compileall tests/test_procore_endpoint_structured_projection_remediation.py scripts/proofs/procore_null_projection_audit.py scripts/proofs/procore_raw_payload_mapping_audit.py`: passed.
- `python -m compileall src tests`: passed.
- `ruff check tests/test_procore_endpoint_structured_projection_remediation.py scripts/proofs/procore_null_projection_audit.py scripts/proofs/procore_raw_payload_mapping_audit.py`: passed.
- `ruff check tests/test_procore_endpoint_structured_projection_remediation.py tests/test_procore_endpoint_reference.py tests/test_procore_live_sync_unverified_fail_closed.py scripts/proofs/procore_null_projection_audit.py scripts/proofs/procore_raw_payload_mapping_audit.py`: passed.
- `ruff check .`: failed on pre-existing unrelated repo-wide lint issues outside the Patch 1 files.
- `pytest tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py -q`: passed.
- `pytest tests/test_procore_endpoint_reference.py tests/test_procore_live_sync_unverified_fail_closed.py tests/test_procore_endpoint_structured_projection_remediation.py -q`: passed.
- `pytest tests -k "procore and (projection or null or raw_payload or change_order or endpoint)" -q`: passed.
- `hb-assistant procore analytics projection-schema-audit --json`: passed with `0` runtime plan/schema mismatches.
- `hb-assistant procore analytics projection-audit --endpoint commitment-change-orders --json`: passed with `0` unknown business field paths.
- `hb-assistant procore analytics projection-audit --endpoint prime-change-orders --json`: passed with `0` unknown business field paths.
- `hb-assistant procore analytics no-raw-leak-scan --path docs/evidence/procore-null-projection-patch1/20260619T064429Z --json`: passed with `0` unsafe findings.

## Non-Goals

No Budget Detail remediation, company_id remediation, live fetch, scheduler refresh, SourceRefreshOrchestrator run, writeback, schema migration, projection registry edit, projection engine edit, or push was performed.
