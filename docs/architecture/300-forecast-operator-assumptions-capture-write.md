# ADR 300 — Forecast operator-assumptions capture (first interactive write surface)

## Status

Accepted.

## Context

The forecast DB-native chain (schema V58/V59/V60/V63/V66 → projectors → gated live-write →
read-model API → UI panel → operator runbook) is complete and read-only end-to-end. Two V66
tables — `forecast_operator_assumptions` and `forecast_required_assumptions` — ship in the schema
but were `schema-only`: no writers, no readers, and deliberately **outside** the gated run-output
projection's table set (the Phase-3 live-write never touches them).

This is the first **net-new interactive write surface** for forecasting: a role-guarded UI + API +
service that lets an operator capture the assumptions and required inputs that feed a forecast.
Operator-entered data cannot be re-derived, so the certify-by-re-derivation model used for
*projected* data (Phases 3/13/14) does not apply here.

No schema/migration/lifecycle-count change — the tables already exist (live DB is past V66).

## Decision

Persist operator-entered assumptions **directly into the managed DB** via a role-guarded FastAPI
route → service → upsert, mirroring the app's existing operator-write pattern
(`add_project_keyword` / `ProjectKeywordsService`). NOT the gated temp-swap-certify projection.

- **Service** `construction/analytics/forecast_operator_assumptions.py`
  (`ForecastOperatorAssumptionsService`): write + read, fail-closed schema gate (`>= 66`), reads via
  `mode=ro` with a business-safe column whitelist, writes via a mutable connection committed in one
  transaction, connections closed in `finally`.
  - `forecast_operator_assumptions`: operator **create** (`assumption_id = uuid4().hex[:12]`, many
    allowed per type) + **edit** (merge provided-or-existing fields, bump `updated_utc` only).
  - `forecast_required_assumptions`: operator **create** (idempotent) + **mark-satisfied**.
- **API** (`construction/analytics/api.py`): four Pydantic request models + a service factory +
  a 503-mapping call wrapper, and six routes under `/api/forecast/db/*` — `GET` lists are
  viewer-readable; `POST`/`PATCH` require `require_operator_role` as the first line.
- **Frontend**: `api.ts` types + six client fns; `ForecastOperatorAssumptionsPanel.tsx`
  (capture form + read tables + required-assumption satisfied toggle) hosted under the existing
  decision-support panel in the Run Center; lists `refetch()` after each write.

### Project-scoped (`run_id` NULL)

These are project-level operator inputs that feed a forecast, not run artifacts, so `run_id` is
always NULL.

### Required-assumption idempotency keyed on PK-hash (not the table UNIQUE)

`forecast_required_assumptions` declares `UNIQUE(run_id, assumption_type)`, but with `run_id` NULL
SQLite treats NULLs as distinct, so that constraint does **not** dedupe. Real idempotency comes from
a deterministic primary key `id = hash_value("{project_key}:{assumption_type}")` upserted via
`ON CONFLICT(id)`. Re-declaring a requirement updates the canonical row rather than inserting a
duplicate. (Operator assumptions, by contrast, have no logical-identity dedupe — many of the same
type are legitimate — so they use a random `assumption_id`.)

### Redaction contract

Read paths SELECT a column whitelist and **never** surface `raw_json` or `run_id`; timestamps render
via `_friendly_utc` (a raw `YYYYMMDD_HHMMSS` stamp would trip the shared leak scan, but `run_id` is
NULL and never selected, so it cannot fire). `forecast_dto.find_redaction_leaks` is the backstop —
service- and endpoint-level tests assert every list payload is leak-free, including against a row
whose stored `raw_json`/`run_id` carries deliberate path + run-stamp bait. The free-text `source`
column is an operator label, not a path; the leak scan catches any pasted absolute path. `raw_json`
is still written (NOT NULL) as a deterministic snapshot of the operator-supplied fields, but stays
internal.

## Consequences

- First forecast surface to write the managed DB outside the gated CLI. Safe because the two tables
  are not in the gated projection's table set, so the Phase-3 tropical-replace cannot clobber them
  and they cannot affect run-output certification.
- Invalid input / not-found return `ok:False` dicts with HTTP 200 (matching the keyword convention);
  only fail-closed unavailability (missing/unreadable DB or schema `< 66`) maps to 503.
- Deferred: seeding "required" items automatically from decision-support gaps; any change to the
  gated projection's table set.
