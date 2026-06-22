# SchemaCrawler Forecasting DB Map Review

## Status

Partial but usable SchemaCrawler package.

## Included

- 01-brief.txt
- 02-schema-maximum.txt
- 04-lint.txt
- 05-forecasting-family-schema.txt
- 99-zero-byte-files.txt

## Coverage

SchemaCrawler discovered the full SQLite schema and produced targeted forecasting-family schema output.

The targeted forecasting-family output covers:
- forecast_* tables
- procore_ep_budget* / procore_ep_billing* tables
- procore_ep_change_events* tables
- procore_ep_commitment* tables
- procore_ep_prime* tables
- procore_ep_purchase_order* tables
- procore_ep_rfqs* / procore_ep_rfq* tables
- procore_ep_subcontractor* tables
- second_brain_financial_forecast_readiness_runs

## Known Gaps

This package does not include:
- JSON SchemaCrawler output
- HTML output
- SVG/PNG diagram output
- run context
- sqlite quick_check output
- explicit no-raw-leak scan output until added after package review

## Modeling Notes

SchemaCrawler lint found same-named columns with different declared data types across tables. Forecast-model design must not assume same-named columns are type-equivalent or semantically equivalent without explicit normalization.
