# Stage 4 — Authoritative owner SOV scope crosswalk

**Artifact:** `config/crosswalks/tropical/owner_sov_scope_crosswalk_tropical_authoritative_20260614_final.jsonl`
(+ `.csv` and `_validation_report.json`).
**Validator:** `src/construction_financial_review/mapping/validate_owner_sov_scope_crosswalk.py`.

The user-approved scope relationships that replace inferred owner/Procore matching. Authoritative —
consumed verbatim, never inferred/overridden. The explicit `covered_budget_code_keys` /
`covered_procore_wbs_flat_codes` lists are the source of truth.

Validated facts: 58 rows · 127/127 budget · 42/42 Procore latest WBS · 0 unresolved · 0 duplicate ·
`20-18-105→1000.20-18-170.MAT` · `99-01-790→1000.90-01-300.MAT` · `15-01-426→1000.15-01-426.MAT` ·
`15-01-530`→LAB/LBN/MAT/SUB · `15-01-XXX` excludes 426*/530* · `10-XX-XXX` description-sensitive (two
disjoint rows).

Validate:

```bash
PYTHONPATH=src python3 -m construction_financial_review.cli validate-crosswalk --project tropical
```

See `schemas/owner_sov_scope_crosswalk_schema.md`.
