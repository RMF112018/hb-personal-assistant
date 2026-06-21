# Forecasting Semantic Catalog

Repo-owned semantic layer design artifacts for forecasting DB evidence and future model implementation.

## Authority

- **Primary evidence:** `docs/evidence/forecasting-db-complete-evidence-*/`
- **Code truth:** `src/hb_assistant/procore/`, `src/hb_assistant/store/`, `src/hb_assistant/construction/analytics/`
- **Field classifiers:** `src/hb_assistant/forecasting/field_classifiers.py`

## Relationship confidence levels

| Level | Meaning |
|-------|---------|
| `high` | Schema + row-profile + repo-code alignment |
| `medium` | Row-profile supported; business semantics partially proven |
| `low` | Schema or naming only; needs validation |
| `unresolved` | Conflicting or insufficient evidence |

## Evidence basis tags

`schema-supported`, `row-profile-supported`, `repo-code-supported`, `Procore-doc-supported`, `inferred`, `unresolved`

## Validation

Run SQL under `validation_queries/` against the local SQLite DB (read-only). Never export raw payload bodies.