# 02 — Structured Endpoint Data Contract

## Objective

Define the Procore analytics storage contract before implementing tables or writes.

The contract must state exactly how each endpoint is captured, identified, stored, reprocessed, projected, and exposed to downstream consumers.

## Required design outputs

Create or update repo resources/docs/tests for a structured endpoint data contract covering endpoint key, family, version/API path shape, live verified status, scope, required params, pagination/envelope, record id, parent id, natural key fallback, source timestamp fields, current-state fields, structured table target, raw payload landing target, child table targets, projection targets, daily-brief eligibility, analytics eligibility, sensitivity, retention, PII policy, signed URL/token scrubbing policy, reprocessing eligibility, and no-writeback posture.

## Storage-layer contract

The package must distinguish these layers:

1. `procore_endpoint_capture_*` control tables.
2. `procore_endpoint_raw_payloads` governed raw landing/snapshot table.
3. `procore_raw_*` or `procore_bronze_*` structured endpoint-family tables.
4. Existing or new `procore_financial_*`, `procore_inspection_*`, `procore_record_edges`, `procore_action_signals`, and analytics/read-model tables.

## Required structured family table plan

At minimum design typed structured tables for RFIs/responses, submittals/responses/packages, observations/punch items, meetings/details/topics, daily logs by subtype, inspections/sections/items, schedules/activities, contracts/commitments/purchase orders/change orders/line items, change events/RFQs/responses/quotes, budget views/detail rows/changes/modifications/amount facts, subcontractor invoices/items/billing periods/payment applications where supported, and attachments/people/companies/locations.

## Required contract tests

Add tests proving every live-verified endpoint maps to a raw landing target; every analytics-eligible endpoint maps to a structured family table or explicit defer reason; every structured table maps back to endpoint contracts; idempotency keys can be computed for parent and child endpoints; source refs can be derived for every endpoint; endpoints with unresolved path/identity fail closed; and no endpoint defaults to unstructured JSON-only storage unless explicitly documented as transitional.

## Evidence

Write evidence under `docs/evidence/procore_endpoint_structured_analytics_foundation/02-structured-endpoint-data-contract/`.
