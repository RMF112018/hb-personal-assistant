# Forecasting Gates Live-Copy Evidence — 20260621T133000Z

## DB copy method

- Source (read-only): `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Copy command: `sqlite3 "$LIVE_DB" "VACUUM INTO '$OUT/live-copy.sqlite';"`
- `PRAGMA quick_check` result: **ok** (see `01-sqlite-quick-check.txt`)
- **The copied SQLite file (`live-copy.sqlite`, ~3.2 GB) is excluded from git** via `.gitignore`.

## Commands run

```bash
scripts/run_forecasting_gates_live_copy_evidence.sh
# or PYTHONPATH=src python gate writers against $OUT/live-copy.sqlite
hb-assistant procore analytics no-raw-leak-scan --path "$OUT" --json
```

## Gate summary (warn mode)

| Gate | ok | findings | warnings | errors |
|------|----|----------|----------|--------|
| forecast_double_count_prevention | true | 790 | 587 | 0 |
| forecast_actuals_reconciliation | true | 0 | 0 | 0 |
| forecast_projection_parity | true | 2 | 2 | 0 |
| forecast_cost_type_guard | true | 1 | 1 | 0 |

Combined (`02-forecast-gates-warn.json`): **4/4 gates passed** with **590 total warnings** (warn mode keeps `ok=true`).

## Strict mode

`03-forecast-gates-strict.json`: **ok=false** — double-count gate promotes 587 workflow/budget overlap warnings to errors. Expected: strict mode is for triage, not production blocking, until Procore formula proof exists.

## Warning categories (triage)

### Double-count (587 warnings)

| Category | Count (capped) | Assessment |
|----------|----------------|------------|
| `budget_column_overlap_revised_budget_with_pending_changes` | 200 | Expected unresolved semantics — calculated rollup may already include pending changes |
| `budget_column_overlap_projected_costs_with_committed_and_direct` | 200 | Expected unresolved semantics — projected costs may include committed/direct |
| `budget_column_overlap_eac_with_projected_costs` | 200 | Info-level coexistence; EAC is terminal rollup |
| `change_event_to_approved_cco_overlap` | 187 | Expected precedence review — CE amounts coexist with approved CCOs |
| `budget_modification_and_change_event_overlap` | 3 | Info — verify budget column precedence |

All budget-column overlap findings carry `procore_formula_proof: unresolved`.

### Projection parity (2 warnings)

- PO row-count mismatch: EP 11 vs financial 16
- 5 keys only in `procore_financial_contracts` (hashed samples in `06-projection-parity-gate.json`)
- Commitment pair: no key-level drift detected in this run

### Cost-type guard (1 warning)

- `cost_type` 100% null on `procore_ep_budget_detail_rows`; `category→cost_type` mapping remains **forbidden**

### Actuals reconciliation

- No material variances flagged against configured thresholds

## No-raw scan

`98-no-raw-leak-scan.json`: **ok=true**, `unsafe_finding_count=0`

## PR readiness

Safe JSON evidence in this folder is suitable for commit. Regenerate the DB copy locally with the documented script; do not commit `live-copy.sqlite`.