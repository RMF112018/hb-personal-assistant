# Patch 5 Purchase-Order Custom-Field Container Evidence

Generated at: `2026-06-19T08:35:35Z`

## Objective

Classify the three purchase-order custom-field bare object/container fields using body-free source-shape metadata and copied-DB replay proof.

## Starting Commit

`c30e4286ba45d0511fd04e5e45e389bb42c49da8`

## Summary

- Target custom-field containers: `3`
- Target scalar destination columns: `4`
- Parent decision counts: `{'covered_by_existing_scalar_decomposition_columns': 3}`
- Scalar status counts: `{'already_replays_existing_scalar_columns': 4}`
- Additional `*_value_label` scalar siblings are comparative metadata only.
- Raw strict findings are not described as fixed; Patch 5 records post-proof dispositions.
- Raw payload values emitted: `false`

## Field Outcomes

| Bare column | Decision | Bare non-null after replay | Comparative siblings |
| --- | --- | ---: | --- |
| `custom_fields_custom_field_214072_value` | `covered_by_existing_scalar_decomposition_columns` | 0 | `custom_fields_custom_field_214072_value_label` |
| `custom_fields_custom_field_214078_value` | `covered_by_existing_scalar_decomposition_columns` | 0 | `custom_fields_custom_field_214078_value_label` |
| `custom_fields_custom_field_214087_value` | `covered_by_existing_scalar_decomposition_columns` | 0 | `custom_fields_custom_field_214087_value_label` |

## Replay Receipt

- `purchase-order-contracts`: ok=`True`, returncode=`0`, primary_rows_written=`11`

## Guardrails

- No raw custom-field values, raw payload bodies, names, emails, notes, comments, descriptions, URLs, signed URLs, credentials, or sample values are emitted.
- Bare custom-field container columns were not reset or newly populated.
- Budget Detail, `company_id`, child-table/entity-only fields, live calls, scheduler, SourceRefreshOrchestrator, writeback, production DB mutation, broad refresh, and push were not used.

## Remaining Decisions After Patch 5

- Future generic custom-field value-table design remains separate.
- Out-of-scope comparative sibling columns require explicit approval before target expansion.
- Raw strict detector findings remain preserved; Patch 5 adds post-proof dispositions only.
