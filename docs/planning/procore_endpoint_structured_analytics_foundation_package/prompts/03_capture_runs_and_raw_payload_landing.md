# 03 — Capture Runs and Raw Payload Landing

## Objective

Implement the governed raw payload landing/snapshot layer and capture-run receipts.

This layer enables replay and full local reprocessing without live Procore calls. It is necessary but not sufficient for analytics; typed endpoint-family tables are implemented in the next prompt.

## Required schema

Add migrations only after fresh and copied DB validation. Use additive migrations. Do not alter or drop existing tables.

Minimum tables: `procore_endpoint_capture_runs`, `procore_endpoint_capture_pages`, `procore_endpoint_raw_payloads`, and optionally `procore_endpoint_capture_errors`.

`procore_endpoint_raw_payloads` must include the fields listed in the README and must support idempotent insert/update by endpoint/project/parent/record/payload hash, current-state selection via `is_current`, historical snapshots via payload hashes and seen timestamps, request fingerprint linking, source ref hash linking, payload size tracking, retention class, security scrub status, analytics eligibility, and strict no-writeback guard columns.

## Security scrubbing

Before persistence, scrub or separate access tokens, refresh tokens, bearer headers, signed URL query strings, private download URLs, known secret-like values, and credentials.

Do not reduce business content to useless hashes. The goal is local analytics-grade persistence. Scrub security-sensitive transport artifacts, not legitimate business fields.

## Capture integration

Integrate at the canonical live-sync boundary so the same endpoint registry/path handling is used. Do not route through stale legacy Procore sync paths unless repo truth says they are authoritative.

Capture must run in dry-run/report mode by default. Apply/persist mode must be explicit and capped.

## Required tests

Migration fresh DB, migration copied DB, idempotent payload insert/update, payload hash stability, source ref hash stability, parent/child identity, security scrub tests, external writeback remains false, no raw payload appears in CLI/evidence/status/daily brief output, and raw landing can be queried for replay without live Procore calls.

## Evidence

Write evidence under `docs/evidence/procore_endpoint_structured_analytics_foundation/03-capture-runs-and-raw-payload-landing/`.
