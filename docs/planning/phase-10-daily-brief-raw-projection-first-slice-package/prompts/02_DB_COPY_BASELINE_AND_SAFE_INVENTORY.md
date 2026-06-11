# 02 — DB-Copy Baseline and Safe Inventory

## Objective

Create a read-only baseline against a copied DB to prove current data state before implementation.

## Steps

1. Create `/tmp` audit root and DB copy.
2. Record production DB hash, size, and mtime before copy.
3. Open the copy in read-only/query-only mode for baseline inventory.
4. Run safe aggregate SQL only.

Use `templates/SAFE_DB_SQL_CHECKS.sql` as a starting point.

## Minimum checks

- `PRAGMA quick_check`
- `SELECT * FROM schema_migrations ORDER BY version`
- `PRAGMA user_version`
- Relevant table inventory and row counts.
- Source-quality distributions for raw and structured tables.
- Projection run/coverage counts.
- Daily brief candidate/source-ref/project-key coverage counts.
- Procore action signal counts by status/type/importance where safe.
- Guard-column sums.

## Evidence

Create:

- `03-db-copy-baseline.json`
- `04-schema-and-migrations.json`
- `05-table-counts-baseline.json`

## Acceptance

- No raw content printed.
- Baseline confirms whether current DB has empty/non-empty structured projection and candidate layers.
- Production DB is not mutated.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
