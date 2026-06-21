# Phase 3 PR Readiness Report — Forecasting Semantic Gates

## Executive summary

Phase 3 moves forecasting semantic gates from isolated implementation to production-ready integration: combined gate runner with stable JSON contract, Phase 08C readiness-chain adapter, live-copy evidence, budget-column role awareness, key-level projection parity, and configurable external-eval project eligibility. All 75 forecasting + normalizer tests pass; Ruff clean.

## Branch / worktree / HEAD

| Field | Value |
|-------|-------|
| Worktree | `/Users/bobbyfetting/hb-personal-assistant-worktrees/forecasting-db-audit-20260621` |
| Branch | `feature/forecasting-db-audit-20260621` |
| HEAD | `264a62969e344e617a56960ca07c8237c0e1bbaf` (pre-commit; will advance on Phase 3 commit) |
| Dirty | Phase 3 implementation + evidence JSON (no live DB committed) |

## Files changed since Phase 2

### New

- `src/hb_assistant/forecasting/readiness.py` — readiness adapter + summary JSON
- `src/hb_assistant/forecasting/project_eligibility.py` — external eval allowlist
- `scripts/run_forecasting_gates_live_copy_evidence.sh`
- `docs/forecasting/semantic-catalog/budget_column_roles.yml`
- `docs/evidence/forecasting-gates-live-copy-20260621T133000Z/` (JSON evidence; DB gitignored)
- `tests/test_forecasting_readiness.py`
- `tests/test_forecasting_projection_parity_keys.py`
- `tests/test_forecasting_project_eligibility.py`

### Modified

- `src/hb_assistant/forecasting/gates.py` — budget column roles, key-level parity, schema-aware columns, combined summary
- `src/hb_assistant/construction/second_brain/financial_completeness.py` — `forecast_semantic_gates` in readiness chain
- `src/hb_assistant/construction/analytics/forecast_external_eval_service.py` — project eligibility + dynamic project_key
- Semantic YAML/SQL, CLI-compatible tests, evidence package test fix

## Live-copy gate evidence

- Evidence: `docs/evidence/forecasting-gates-live-copy-20260621T133000Z/`
- Triage: `README.md` in that folder
- Warn mode: 4/4 gates ok, 590 warnings (mostly expected unresolved budget/CE precedence)
- Strict mode: fails on double-count (587 promoted warnings) — documented, not production-blocking
- No-raw scan: pass

## Gate integration

- `evaluate_forecast_semantic_gates()` in `forecasting/readiness.py`
- Wired into `evaluate_forecast_readiness_gates()` as gate `forecast_semantic_gates`
- CLI unchanged: `construction-agent forecast gates` returns combined JSON with `summary` block
- Individual gate commands preserved

## Budget calculated-column double-count

- `budget_column_roles.yml` documents additive vs non-additive columns
- Double-count gate runs three overlap checks with `procore_formula_proof: unresolved`
- Tests: `test_double_count_budget_column_role_overlap`

## Projection parity

- Count-level checks retained
- Key-level: missing source/target keys (hashed samples), status mismatches
- Tests: `test_projection_parity_key_level_findings`

## External forecast project generalization

- `_SUPPORTED_PROJECT` replaced with `project_eligibility.py`
- Default allowlist: `tropical`, `fixtureproj`
- Override: `HB_FORECAST_EVAL_PROJECT_ALLOWLIST=proj1,proj2`
- `evaluate()` validates eligibility; package/manifest/eval DB use passed `project_key`

## Tests run

```text
pytest tests/test_forecasting_*.py tests/test_procore_normalizers_financial_amounts.py -q  → 75 passed
ruff check src/hb_assistant/forecasting/ tests/test_forecasting_*.py  → clean
```

Live-copy script documented; not run in CI against live DB.

## Remaining unresolved issues

1. **Procore budget formula proof** — overlap warnings are expected; cannot hard-fail without official inclusion rules
2. **`category` → `cost_type`** — 100% null cost_type on live budget rows; equivalence unproven; mapping forbidden
3. **PO projection drift** — 5 financial-only PO keys; needs relationship audit, not auto-repair
4. **Strict mode** — promotes semantic warnings to errors; use warn mode for readiness reporting

## Risk exposure

- Low: read-only gates, no live DB mutation, no Procore writeback
- Medium: large warning volume on live data may be misread as defects — triage README clarifies expected vs defect

## Standards preserved

- No raw payload export in gate JSON
- No `category`→`cost_type` inference
- Conservative unknown/null handling
- Additive schema/docs/tests only

## PR checklist

- [x] No raw payloads exposed in committed evidence
- [x] No live DB committed (`live-copy.sqlite` gitignored)
- [x] No Procore writeback
- [x] Gates runnable from CLI (`construction-agent forecast gates`)
- [x] Gates tested on synthetic fixtures
- [x] Gates run against copied live DB; safe JSON captured
- [x] Semantic docs updated (`budget_column_roles.yml`)
- [x] Tests pass (75)
- [x] Ruff passes
- [x] Remaining warnings documented in triage README