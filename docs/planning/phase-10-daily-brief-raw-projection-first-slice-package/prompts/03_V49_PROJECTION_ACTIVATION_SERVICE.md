# 03 — V49 Projection Activation Service/Stage

## Objective

Implement or harden a small projection activation service that daily-run and CLI surfaces can call to project V49 email/calendar raw rows into structured rows safely.

## Implementation guidance

Prefer a narrow wrapper around existing `email_calendar.projection_engine` rather than duplicating projection logic.

The wrapper/stage should:

- Accept explicit `db_path`.
- Support dry-run and apply modes.
- Never make Graph calls.
- Never perform external writeback.
- Refuse unsafe production apply unless invoked through an intentional daily-run apply path or explicit operator command already designed for production use.
- Return a structured receipt with:
  - raw row counts by family
  - structured row counts before/after
  - projection run ids when applied
  - coverage status
  - unmapped counts
  - skipped higher-quality counts
  - source-quality distribution
  - degraded/failure reason codes
  - guardrail flags

## Required code behavior

- If no raw rows exist, report `no_raw_rows` without failure.
- If raw rows exist and projection fails due to unmapped fields, report degraded/failed clearly.
- If raw rows exist and structured rows remain zero after apply, report degraded/failed clearly.
- Do not emit raw values in receipts.

## Tests

Add tests proving:

- Dry-run writes nothing.
- Apply against temp DB writes structured rows and receipts.
- Unmapped path failure degrades/fails without partial projection.
- Lower-quality raw rows cannot downgrade structured rows.
- Receipt contains counts/status only.

## Evidence

Generated later by Prompt 13:

- `06-v49-projection-dry-run.json`
- `07-v49-projection-apply-copy.json`
- `08-v49-projection-coverage-after.json`

## Acceptance

- Projection activation is callable from daily-run integration without raw leaks.
- Existing email-calendar CLI still works.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
