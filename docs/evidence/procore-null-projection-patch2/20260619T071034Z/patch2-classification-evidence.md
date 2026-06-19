# Procore Null Projection Patch 2 Classification Evidence

Timestamp: `20260619T071034Z`

## Objective

Patch 2 is classification/reporting only. It preserves raw strict detector facts while adding post-proof dispositions for remaining Procore null projection findings.

Target closeout position:

Raw strict detector still identifies nullable/all-null/schema-interest fields, but Patch 2 adds evidence-backed dispositions showing 0 remaining high-confidence raw-payload-backed scalar mapping candidates, 0 date/datetime mapping candidates, and 0 Patch 1 scalar decomposition defects. Remaining fields are classified as object/container design decisions, source-absent fields, company_id policy deferrals, Budget Detail no-action/read-model artifacts, or expected optional fields.

## Files Changed

- `scripts/proofs/procore_null_projection_audit.py`
- `scripts/proofs/procore_raw_payload_mapping_audit.py`
- `tests/test_procore_null_projection_audit.py`
- `tests/test_procore_raw_payload_mapping_audit.py`
- `docs/evidence/procore-null-projection-final-schema-decision-matrix/20260619T000000Z/remaining-unresolved-schema-decision-matrix.md`

## Classifier Buckets Implemented

- `object_container_requires_decomposition_or_deprecation`
- `source_absent_in_current_payloads`
- `company_id_policy_deferred`
- `budget_detail_dead_convenience_column`
- `budget_detail_read_model_schema_artifact`
- `expected_optional_no_action`
- `date_sweep_clear`
- `patch1_scalar_decomposition_verified`
- `no_current_mapping_action`

The audit now emits both raw facts and post-proof decisions:

- `raw_detection.suspected_projection_defect`
- `raw_detection.root_cause_class`
- `raw_detection.classification`
- `post_proof_decision.decision_class`
- `post_proof_decision.decision_status`
- `post_proof_decision.mapping_candidate`
- `post_proof_decision.next_action`
- `post_proof_decision.evidence_basis`

## Post-Patch-2 Counts

| Metric | Count |
| --- | ---: |
| Raw suspected projection defects preserved | 123 |
| High-confidence raw-payload-backed scalar mapping candidates | 0 |
| Date/datetime mapping candidates | 0 |
| Patch 1 scalar decomposition defects | 0 |
| Object/container design decisions | 43 |
| Source-absent fields | 67 |
| Company ID policy deferrals | 4 |
| Budget Detail dead convenience columns | 4 |
| Budget Detail read-model artifacts | 4 |
| Expected optional/no-action fields | 463 |
| Patch 1 scalar decomposition fields verified | 14 |

## Decision Notes

- Patch 1 fields are recognized as `patch1_scalar_decomposition_verified` only when present in audit/source-proof scope. They are not forced into the remaining raw 123-count reconciliation.
- Budget Detail remains no-action. Row convenience fields are dead/convenience candidates; `currency_iso_code` is expected optional; `visible` and Budget Detail `company_id` columns are read-model artifacts. `data_type`, `name`, and `position` remain already populated and untouched.
- Standard `company_id` findings remain policy-deferred. No global derivation or backfill was performed.
- Object/container columns remain design decisions for decomposition or deprecation. No dict/list payload was projected into a bare scalar column.
- Source-absent fields remain unmapped until future endpoint-limited source evidence proves otherwise.
- Date/datetime sweep remains clear with 0 source-backed unmapped date candidates.

## Validation

- `python -m compileall scripts/proofs/procore_null_projection_audit.py scripts/proofs/procore_raw_payload_mapping_audit.py tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py`: passed.
- `ruff check scripts/proofs/procore_null_projection_audit.py scripts/proofs/procore_raw_payload_mapping_audit.py tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py`: passed.
- `pytest tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py -q`: passed.
- `pytest tests -k "procore and (projection or null or raw_payload or schema or endpoint)" -q`: passed.
- `python -m compileall src tests`: passed.
- `hb-assistant procore analytics projection-schema-audit --json`: passed with 0 mismatches.
- `hb-assistant procore analytics projection-audit --endpoint commitment-change-orders --json`: passed with 0 unknown business paths.
- `hb-assistant procore analytics projection-audit --endpoint prime-change-orders --json`: passed with 0 unknown business paths.
- `hb-assistant procore analytics no-raw-leak-scan --path docs/evidence/procore-null-projection-patch2/20260619T071034Z --json`: passed with 0 unsafe findings.
- `ruff check .`: failed on pre-existing unrelated repo-wide lint issues outside Patch 2 touched files.

## Non-Goals Confirmed

- No schema migration.
- No projection registry edit.
- No projection engine mapping or write-path edit.
- No Budget Detail refresh/reconciliation change.
- No `company_id` derivation or backfill.
- No live Procore calls.
- No scheduler, `SourceRefreshOrchestrator`, all-project refresh, or all-endpoint refresh.
- No Procore writeback.
- No raw payload bodies, payload fragments, sample values, names, emails, notes, comments, descriptions, signed URLs, credentials, or business text emitted.
- No push.
