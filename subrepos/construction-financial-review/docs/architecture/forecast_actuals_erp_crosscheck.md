# Actuals ERP Cross-Check

## Purpose

`actuals-erp-crosscheck` emits additive reconciliation evidence comparing calculated CostEntries
actual cost-to-date to BudgetDetails ERP job-to-date cost by canonical `budget_code_key`.

CostEntries/Sage incurred cost remains transaction-level accounting truth. BudgetDetails ERP
job-to-date values are reconciliation evidence only; they never overwrite calculated actuals, set an
actuals floor, cap forecast values, or change forecast model outputs.

## Inputs and Lineage

The command resolves the configured `forecast_context_package` from `config/projects/tropical.json`
under the active Tropical `default_data_root`; it does not blindly consume the latest matching context
folder. The package lineage audit records:

- context package path and whether it is under the active data root
- context manifest project metadata, generated stamp, and validation status
- source hashes before and after the run
- actuals cutoff date inferred from mapped CostEntries accounting dates

Calculated actuals come from `canonical/cost_entries.jsonl`. Only rows mapped to a canonical
`budget_code_key` are summed. Canonical keys with no mapped CostEntries are valid zero-actual keys and
are emitted as `0.00`, not as missing actuals.

Monthly reconciliation uses `canonical/monthly_actuals_by_budget_code.jsonl` rows whose source is
`CostEntries`. The month key is `YYYY-MM`, using the canonical monthly actuals export and CostEntries
accounting month/date fields. Negative corrections and credits are included because rows are summed
as signed Decimal amounts.

## ERP Field

The explicit ERP candidate field is:

`BudgetDetails.amounts.erp_job_to_date_costs`

The cross-check audits this field before using it. It is treated as comparable only when the configured
field is exactly `amounts.erp_job_to_date_costs`, appears on canonical BudgetDetails rows, and the
canonical comparison layer has no duplicate ERP rows after normalization. Budget, committed cost,
projected cost, retainage, and current-period-only fields are not used.

## Outputs

The command writes:

`actuals_erp_crosscheck_package_tropical_<stamp>/`

Key files:

- `actuals_erp_crosscheck_by_budget_code.jsonl`
- `actuals_erp_crosscheck_summary.json`
- `actuals_monthly_reconciliation_by_budget_code.jsonl`
- `actuals_monthly_reconciliation_by_month.csv`
- `actuals_erp_crosscheck_variances.csv`
- `audit/actuals_source_lineage_audit.json`
- `audit/actuals_mapping_audit.json`
- `audit/actuals_month_assignment_audit.json`
- `audit/actuals_erp_cost_to_date_field_audit.json`
- `audit/actuals_erp_variance_audit.json`
- `audit/actuals_monthly_sum_to_date_audit.json`
- `audit/actuals_crosscheck_validation_report.json`
- `validation_report.json`
- `manifest.json`

The manifest includes all emitted files, source package path, source hashes, config used, frozen stamp,
advisory/strict mode, and validation status.

## Validation Posture

Default mode is advisory: material dollar variances are warnings and evidence, not a package-generation
blocker. Strict mode fails closed on material variance and configured structural failures.

Structural failures that make actuals unreliable may fail even outside strict mode. Examples include
canonical mapping failures configured as fail-closed, malformed actual amount inputs, contaminated
monthly actual sources, duplicate canonical ERP rows, and a context package outside the active data
root.

Monthly reconciliation distinguishes:

- `exact_match`
- `rounding_only_variance`
- `material_mismatch`

Per-key ERP variance status uses:

- `matched`
- `rounding_only`
- `material_variance`
- `missing_erp_cost_to_date`
- `missing_calculated_actual`
- `mapping_missing`
- `not_comparable_cutoff_mismatch`
- `not_comparable_granularity_mismatch`
- `not_comparable_field_semantics`
