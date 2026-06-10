# Validation Matrix — Relationship / Entity Normalization (Prompt 07)

| Area | Command / Method | Expected | Actual | Status |
|---|---|---|---|---|
| Compile | `compileall relationship_entity_report.py second_brain.py` | pass | COMPILE_OK | ✅ |
| New regression | `pytest tests/test_phase_10_relationship_entity_report.py` | pass | 4 passed | ✅ |
| Targeted tests | `pytest -k "relationship or entity or alias or dedupe or candidate"` | pass | 287 passed | ✅ |
| Lint | `ruff check <changed>` | pass | All checks passed | ✅ |
| Types | `mypy relationship_entity_report.py` | pass | no issues | ✅ |
| Report grouping | seeded temp DB | 5 categories | alias 2 / rel 2 / dup 2 / needs-review 1 / rejected 1 | ✅ |
| Dedupe proof | same-entity candidates | grouped as duplicates | dup1+dup2 | ✅ |
| Alias-match proof | project candidates | grouped as alias/project | proj1+proj2 | ✅ |
| Low-confidence | weak/model-proposed/review-required | routed to needs-review (advisory) | nr1 | ✅ |
| Daily-brief context | unreviewed not promoted | promotion-safety ok | true | ✅ |
| Dry-run / read-only | rows before/after | unchanged | true | ✅ |
| Guard columns | sum of 8 V25 guards | zero | nonzero_sum=0 | ✅ |
| Safety scan | forbidden-pattern scan | no findings | TOTAL_FINDINGS=0 | ✅ |
| Production DB checksum | sha256 before/after | unchanged | UNCHANGED=True | ✅ |
| DB migration | N/A | — | no schema change | ✅ N/A |

Notes: grouping is deterministic (stable enums, no model). The report is read-only and never promotes;
the actual bounded apply remains `relationship-candidates scan --apply --max-persist`. All reporting
ran on a disposable temp DB; production read once, never written.
