# 04 — Typed Endpoint-Family Structured Tables

## Objective

Implement structured endpoint-family tables for Procore analytics.

This is the core of Bobby's correction: raw Procore data must be captured in structured tables for future analytics. A generic raw JSON table alone is not acceptable.

## Required implementation pattern

For each endpoint family, define a typed structured table or child-table set; include stable identity, project/company identity, endpoint identity, source timestamps, capture timestamps, payload hash, and raw payload linkage; preserve analytics-relevant business fields in typed columns; keep nested arrays in child tables when analytically important; add indexes for common analytics filters; add mappers from raw landing payloads to typed tables; add idempotent upsert behavior; and add tests using representative payload fixtures.

## Minimum structured table families

Implement or explicitly reconcile with existing typed tables for:

- RFIs: `procore_raw_rfis`, `procore_raw_rfi_responses`.
- Submittals: `procore_raw_submittals`, `procore_raw_submittal_responses`, `procore_raw_submittal_packages`.
- Observations and punch: `procore_raw_observations`, `procore_raw_punch_items`.
- Meetings: `procore_raw_meetings`, `procore_raw_meeting_topics`, and child tables for attendees/assignments/decisions/history when payload supports them.
- Daily logs: `procore_raw_daily_logs` and subtype-specific child details where needed.
- Inspections: reconcile or extend `procore_inspection_records`, `procore_inspection_sections`, `procore_inspection_items` as bronze/silver split, or add `procore_raw_inspection_*` tables. Do not lose raw checklist question/response/business text needed for analytics.
- Schedule: `procore_raw_schedules`, `procore_raw_schedule_activities`.
- Financial/contract/budget/invoice: reconcile existing `procore_financial_*` tables with the new raw/bronze plan and add missing raw structured tables where current tables are silver projections only.
- Dimensions/reference: attachments, companies, people, locations, cost codes/WBS where available.

## Required coverage report

Add a coverage report that answers for each endpoint: captured raw landing rows, structured table rows, current rows, historical snapshot rows, projection rows, source refs, analytics eligible yes/no, daily brief eligible yes/no, and coverage gap reason.

## Required tests

One mapper test per endpoint family, parent-child identity tests, idempotent upsert tests, current-vs-history tests, indexes/schema tests, structured row count alignment to raw landing count or documented gap, and no raw leakage to evidence/status/daily brief.

## Evidence

Write evidence under `docs/evidence/procore_endpoint_structured_analytics_foundation/04-typed-endpoint-family-tables/`.
