# Live metric formula proof summary

- **project:** `tropical`
- **requested version:** `tropical|TWNU19|2026-06-23T08:00:00`
- **resolved version:** `tropical|1071|2026-06-23 08:00` (1507 activities)
- **copy DB:** `local-sensitive/clean-db/tropical-metric-proof-live-copy.sqlite` (sqlite `.backup` from live)
- **shadow recompute:** `pass_fixture` — 3 traces matched (progress count, SPI duration, critical indices)
- **activation matrix:** 20 rows, 0 cross-check findings
- **live DB mutation:** none (`02-live-db-compare.json` passed)

## Shadow operands (live)

| Metric | Numerator | Denominator | Result |
|--------|-----------|-------------|--------|
| progress (activity count) | 795 | 1507 | 0.528 |
| SPI (duration) | 73600 | 98848 | 0.745 |
| critical indices | 0 | 1507 | 0.0 |

## Limitations

- Health/feasibility composites: `pass_with_policy_limitations` (weights not business-validated)
- UDF-dependent metrics may be `not_computable_missing_udf` where normalization absent
- Near-critical requires prior CPM run pair
- Baseline delay requires selected baseline state
