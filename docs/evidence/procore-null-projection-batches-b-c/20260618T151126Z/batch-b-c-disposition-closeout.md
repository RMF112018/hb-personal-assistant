# Batch B/C Null Projection Disposition Closeout

## Summary

- Worktree: `/Users/bobbyfetting/hb-personal-assistant-worktrees/procore-null-projection-batch1`
- Branch: `codex/procore-null-projection-batch1`
- Scope executed: Batch B and Batch C disposition/classifier closeout.
- Projection remediation applied: no.
- Schema, registry, migration, scheduled refresh, live fetch, SourceRefreshOrchestrator, Budget Detail refresh/reconciliation, writeback, or push used: no.
- Raw payload bodies, fragments, sample values, business-sensitive text, credentials, signed URLs, comments, notes, descriptions, or full emails emitted: no.

## Post-B/C Audit Result

| metric | count |
| --- | ---: |
| tables audited | 86 |
| columns audited | 3694 |
| all-null fields | 579 |
| mostly-null fields | 67 |
| suspected projection defects | 0 |
| expected optional fields | 279 |
| support/guardrail fields | 1040 |
| empty tables | 4 |
| explicitly deferred fields | 123 |

## Deferred Field Disposition

| disposition | count |
| --- | ---: |
| documented object-container or child-field decomposition | 29 |
| deferred broad company_id policy | 74 |
| deferred Budget Detail convenience or optional field | 6 |
| documented schema artifact or expected optional | 14 |

## Batch Groups

| batch | count | action |
| --- | ---: | --- |
| Batch A | 2 | Completed earlier by endpoint-limited punch-items replay evidence. |
| Batch B | 29 | Documented as object/container fields already decomposed into scalar child fields or child rows; no bare object-container mapping added. |
| Batch C | 94 | Documented as broad company_id policy, Budget Detail convenience/optional fields, expected optional fields, or schema artifacts; no projection mapping added. |

## Budget Detail Confirmation

| table | rows | suspected projection defect columns |
| --- | ---: | ---: |
| procore_ep_budget_detail_rows | 2496 | 0 |
| procore_ep_budget_detail_row_cells | 225131 | 0 |

Budget Detail refresh/reconciliation remains unchanged. The accepted Budget Detail dynamic read model was not modified.

## Validation

| check | result |
| --- | --- |
| `python -m compileall scripts/proofs/procore_null_projection_audit.py tests/test_procore_null_projection_audit.py` | pass |
| `ruff check scripts/proofs/procore_null_projection_audit.py tests/test_procore_null_projection_audit.py` | pass |
| `pytest tests/test_procore_null_projection_audit.py -q` | pass, 4 tests |
| `python -m json.tool docs/evidence/procore-null-projection-batches-b-c/20260618T151126Z/procore-null-projection-post-bc-audit.json` | pass |
| `hb-assistant procore analytics projection-schema-audit --json` | pass, 0 mismatches |
| `hb-assistant procore analytics projection-audit --endpoint punch-items --json` | pass |
| `hb-assistant procore analytics projection-audit --endpoint prime-contracts --json` | pass |
| `hb-assistant procore analytics projection-audit --endpoint change-events --json` | pass |
| `hb-assistant procore analytics no-raw-leak-scan --path docs/evidence/procore-null-projection-batches-b-c/20260618T151126Z --json` | pass, 0 unsafe findings |

## Evidence Files

- `procore-null-projection-post-bc-audit.json`
- `procore-null-projection-post-bc-audit.md`
- `batch-b-c-disposition-closeout.md`

## Closeout

No schema, registry, migration, projection, scheduled-refresh, live-fetch, SourceRefreshOrchestrator, Budget Detail refresh/reconciliation, Procore writeback, or read-model remediation was applied by this Batch B/C disposition closeout.
