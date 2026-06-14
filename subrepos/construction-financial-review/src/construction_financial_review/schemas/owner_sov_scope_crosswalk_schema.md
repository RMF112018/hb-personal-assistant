# Authoritative owner SOV scope crosswalk — schema reference

The authoritative, user-approved scope crosswalk. Consumed verbatim — never inferred, fuzzy-matched, or
overridden. The **explicit** `covered_budget_code_keys` / `covered_procore_wbs_flat_codes` lists are the
source of truth; `*_patterns` and `*_exclusion_patterns` are human-readable provenance only.

## Row fields
`crosswalk_id`, `mapping_version`, `owner_sov_code`, `owner_cost_code_family`, `owner_scope_description`,
`owner_description_match_rule`, `scope_relationship` {one_to_one, one_to_many}, `coverage_type`
{direct, summary_parent, same_cost_code_multi_category}, `comparison_level` {budget_code,
owner_scope_rollup, cost_code_rollup}, `allocation_required` (bool), `allocation_method`,
`allocation_percent_by_budget_code`, `covered_budget_code_key_patterns`, `covered_budget_code_keys`,
`covered_budget_code_exclusion_patterns`, `covered_procore_wbs_flat_code*`,
`covered_procore_or_budget_code_values`, `comparison_basis`, `confidence`, `approved_by`,
`approved_date`, `notes`.

## Validated facts (final crosswalk)
- 58 rows · 127/127 canonical BudgetDetails coverage · 42/42 Procore latest WBS coverage.
- 0 unresolved owner SOV rows · 0 duplicate-covered budget codes.
- `20-18-105` → `1000.20-18-170.MAT`; `99-01-790` → `1000.90-01-300.MAT`.
- `15-01-426` → `1000.15-01-426.MAT`; `15-01-530` → LAB/LBN/MAT/SUB.
- `15-01-XXX` excludes `1000.15-01-426*` and `1000.15-01-530*`.
- `10-XX-XXX` is description-sensitive (two disjoint rows: GENERAL REQUIREMENTS vs non-GR).

Validated by `mapping/validate_owner_sov_scope_crosswalk.py` (CLI: `validate-crosswalk --project tropical`).
