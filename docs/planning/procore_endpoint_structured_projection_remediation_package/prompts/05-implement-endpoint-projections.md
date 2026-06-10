# 05 — Implement Endpoint Projections

## Goal

Implement projections for all endpoint families, not just change events.

## Required endpoint families

Cover every endpoint in the registry, including but not limited to:

- foundation/projects
- rfis and rfi-responses
- submittals, submittal-responses, submittal-packages
- observations
- meetings, meeting-detail, meeting-topics
- daily logs
- punch items
- schedules and activities
- inspections, inspection sections, inspection items
- owner contracts and prime change orders
- commitments and commitment change orders
- purchase orders
- owner billing/payment applications
- subcontractor invoices and invoice detail items
- change events, change event comments
- RFQs, RFQ responses, RFQ quotes
- budget views, columns, rows, modifications, changes

## Required proof per endpoint

For each endpoint with available full raw payloads:
- parent record count matches projection parent table count,
- each observed nested array has matching child rows,
- every observed primary/nested field path has a destination,
- null rates are computed and explained,
- zero unmapped business fields.

For endpoints without available full raw payloads:
- status must be `no_full_payload_available`, `held`, `no_data`, or `permission/path blocked`.
- Do not guess schema solely from docs; use payloads, fixtures, or endpoint contracts if available.
