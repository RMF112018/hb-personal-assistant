# 08 — DB-Copy Validation and Evidence

## Goal

Prove the implementation works on a `/tmp` copy of the production DB without mutating production.

## Required steps

1. Resolve production DB path.
2. Record production sha256.
3. Copy DB to `/tmp`.
4. Apply migrations to copy.
5. Run projection inventory on copy.
6. Run projection reprocess on copy.
7. Run projection coverage on copy.
8. Prove unmapped business field count is zero for every endpoint with full raw payloads.
9. Record production sha256 again and prove unchanged.

## Evidence files

Write:

- `03-db-copy-validation.md`
- `04-projection-coverage-summary.md`
- `05-unmapped-field-report.md`
- `06-endpoint-row-count-matrix.md`
- `07-null-rate-matrix.md`

Evidence must include counts, field paths, and table names only. Do not write raw field values or payload bodies.
