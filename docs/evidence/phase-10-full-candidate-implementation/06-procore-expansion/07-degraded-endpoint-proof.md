# Degraded / missing endpoint honesty proof

- degraded/unverified endpoints (not live-verified): `budget-change-line-items, budget-details, purchase-order-detail-line-items`
- PRJ-EMPTY verdict: **no_data** (no persisted procore_live_* rows for this project (never synced or unmapped))
- PRJ-STALE verdict: **stale** (no current endpoints; operational data is stale (some never synced))

Missing data and unverified endpoints are reported explicitly; the monitor never presents stale or absent data as current.
