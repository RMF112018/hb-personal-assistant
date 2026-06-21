# Phase 5 Baseline Summary

## Branch context

| Field | Value |
|-------|-------|
| Branch | `feature/forecasting-db-audit-20260621` |
| HEAD SHA | `86f31c6206ecac54f941534c517dbb2b6a18c47c` |
| Worktree | `/Users/bobbyfetting/hb-personal-assistant-worktrees/forecasting-db-audit-20260621` |
| Dirty state | Yes — Phase 5 implementation in progress; unrelated 08c evidence side-effects and untracked tgz bundles excluded from Phase 5 commit |

## Phase 4 status

Phase 4 is **committed** on this branch (`37d13ee9`, merged via `86f31c62`). Main includes Phase 4 at `c313e904` (#72).

Phase 4 artifacts reviewed:

- `docs/evidence/forecasting-db-audit-20260621/phase4-completion-report.md`
- `docs/evidence/forecasting-db-audit-20260621/phase4/`
- `docs/evidence/forecasting-db-audit-20260621/procore-budget-formula-proof.md`
- `docs/evidence/forecasting-db-audit-20260621/purchase-order-projection-drift-audit.md`
- `docs/evidence/forecasting-db-audit-20260621/phase4-projection-parity-design.md`
- Semantic catalog v2 (`budget_column_roles.yml`, validation SQL, gates)

## Remaining open items (Phase 4 carry-forward)

1. `actual_cost` / ERP actual column mapping to Procore semantics
2. Custom/dynamic budget-view columns
3. Additional parity pairs: prime contracts, change events, invoices (RFQs scoped)
4. GitHub Actions workflow or CI equivalent

## Phase 5 intended scope

| Workstream | Deliverable |
|------------|-------------|
| WS1 | This baseline report |
| WS2 | Actual/ERP semantics audit + enhanced actuals gate + tests |
| WS3 | Dynamic budget column catalog + gate + tests |
| WS4 | Projection parity expansion (prime, change event, invoice; RFQ unsupported documented) |
| WS5 | `.github/workflows/forecasting-semantic-gates.yml` + `scripts/ci_forecasting_semantic_gates.sh` |
| WS6 | `docs/evidence/forecasting-db-audit-20260621/phase5/` evidence bundle |
| WS7 | Full test suite + Ruff |
| WS8 | Phase 5 completion report |

## Explicit exclusions

- No live production SQLite mutation
- No Procore write-back
- No copied DB committed
- No raw payload bodies in evidence
- 08c financial-readiness test side-effect JSON (pre-existing dirty files)
- Untracked `forecasting-db-complete-evidence-*.tgz` archives
- RFQ full parity (EP scope subset vs financial projection — documented as unsupported)
- `actual_cost` formula proof (remains unresolved; population evidence only)