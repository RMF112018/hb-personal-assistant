# 11 — CLI Operator Surfaces and Runbook Commands

## Objective

Expose safe operator commands for running and diagnosing the first slice.

## Required CLI surfaces

Inspect existing CLI grouping and add minimally invasive commands/options as needed.

Required capabilities:

1. Projection status and coverage.
2. Projection reprocess dry-run/apply with explicit DB path for copy validation.
3. Calendar candidate build dry-run/apply with cap and DB path/test injection if supported.
4. Procore digest build dry-run/apply with cap and DB path/test injection if supported.
5. Daily-run status/diagnostics showing first-slice gates.
6. Source-ref/usefulness scorecard command or status block.

If some capabilities already exist, document their exact commands and avoid duplicates.

## CLI safety

- Dry-run default.
- Apply requires explicit opt-in and caps where rows are persisted.
- DB-copy validation must support explicit `--db` where practical.
- No command emits raw values.

## Evidence

Create:

- `18-status-json-proof.json`
- `19-cli-help-snapshots.md`

## Acceptance

- Operator can manually validate the slice without reading code.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
