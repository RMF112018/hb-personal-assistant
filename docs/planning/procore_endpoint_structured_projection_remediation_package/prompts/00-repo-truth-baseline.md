# 00 — Repo Truth Baseline

## Goal

Establish exact repo truth before implementing endpoint-specific structured projection remediation.

## Required actions

1. Confirm branch and base:
   - start from current `main`,
   - create `fix/procore-endpoint-specific-structured-projections`,
   - record base SHA.

2. Inventory Procore code paths:
   - endpoint registry,
   - live sync,
   - raw payload persistence,
   - structured analytics,
   - migrator/schema,
   - CLI commands,
   - daily brief/read-model consumers,
   - tests and fixtures.

3. Confirm PR #18 behavior:
   - full raw payloads are persisted to `procore_endpoint_raw_payloads`,
   - source-quality precedence exists,
   - legacy replay cannot downgrade full raw projections,
   - no raw body emission.

4. Inventory existing tables:
   - `procore_endpoint_raw_payloads`,
   - all `procore_raw_*` tables,
   - all dimensions/bridge tables,
   - all Procore read models.

5. Identify schema head and migration pattern.

## Evidence output

Write:

`docs/evidence/procore_endpoint_structured_projection_remediation/00-repo-truth-baseline.md`

Include counts, file paths, function names, schema head, and table names only. No payload bodies.
