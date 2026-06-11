# 04 — Daily-Run Projection Integration and Receipts

## Objective

Integrate V49 projection activation into the daily-run pipeline before candidate projection and model/context assembly.

## Required behavior

Daily-run should follow this order where applicable:

1. Source refresh/raw ingest stages already present.
2. V49 email/calendar raw → structured projection status/dry-run/apply stage.
3. Calendar and Procore candidate projection stages.
4. Source-ref/usefulness gates.
5. Context packet/model/render/status stages.

## Mode policy

- In dry-run/preview: projection stage runs in dry-run mode and reports what would happen.
- In apply mode: projection stage can apply to the configured DB only through the intentional daily-run apply pathway; validation must use a copied DB.
- If CLI already has `--db` override for testing, use it for copy validation.

## Receipt/status fields

Add to daily-run receipt/status JSON:

- `email_calendar_projection.status`
- `raw_rows_by_family`
- `structured_rows_by_family`
- `projection_coverage_status`
- `unmapped_counts`
- `source_quality_distribution`
- `projection_degraded_reason`

## Degradation rules

- Projection failure should not be hidden under clean success.
- If raw rows exist and projection is required but fails, daily-run must be degraded/failed according to existing status taxonomy.
- If projection succeeds but candidate projection later produces zero candidates while useful source data exists, the usefulness gate handles contradiction.

## Tests

Add tests around daily-run orchestration using fake stores/temp DBs to prove ordering and receipts.

## Acceptance

- Daily-run receipts make projection execution or skip explicit.
- Projection failure cannot be mistaken for success.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
