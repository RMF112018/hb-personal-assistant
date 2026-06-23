# P2b — Operator dollar value-overrides · Evidence

All proofs generated against **temporary SQLite DBs** (copied-DB evidence; the live managed DB was
never read or written by this script). Flag: `HB_FORECAST_ASSUMPTION_OVERRIDES_ENABLED=1`.

## Files
- `header_before_after.json` — `projected_cost_override` on code 01-100 (125000 -> 150000): EAC moves
  205000 -> 230000 and variance_to_budget 25000 -> 50000; an `operator_value_override` change row is
  emitted (delta 25000.00); the code row's `raw_json` still shows the ORIGINAL 125000.00 (parity-safe).
- `flag_off_noop.json` — an empty override list yields a planned dict **byte-identical** to baseline
  (the guarded post-pass does not run). Regression-safety proof.
- `apply_parity.json` — `project_run_output` reads the override read-only from a seeded temp
  assumptions DB, applies it to a temp v63 DB: the overridden projected cost + re-aggregated EAC
  persist, and DB<->package **parity is proven** (raw_json round-trips).

## Scope
Dollar value-overrides in `output_projection_engine` only (reserved types
`projected_cost_override` / `cost_to_complete_override`). No schema change; no live-DB write. See ADR 302.
