# Procore Monitoring Report

_Generated 2026-06-09T12:00:00+00:00 · stale threshold 7d · read-only, no live call._

## Endpoint contract
- endpoints: 59 · live-verified: 56 · degraded/unverified: 3
- degraded endpoints: budget-change-line-items, budget-details, purchase-order-detail-line-items

## Overall
- verdict: **no_data** · projects: 3 (healthy 0 · partial_stale 1 · stale 1 · no_data 1)

## Per project
- **PRJ-FRESH** → verdict **partial_stale** · current 1 · stale 0 · never 55
  - 55 endpoint(s) stale/never-synced; 1 fresh
  - stale `billing-periods` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-FRESH --endpoint billing-periods --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-change-history` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-FRESH --endpoint budget-change-history --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-detail-columns` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-FRESH --endpoint budget-detail-columns --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-detail-rows` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-FRESH --endpoint budget-detail-rows --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-modifications` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-FRESH --endpoint budget-modifications --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
- **PRJ-STALE** → verdict **stale** · current 0 · stale 1 · never 55
  - no current endpoints; operational data is stale (some never synced)
  - stale `billing-periods` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-STALE --endpoint billing-periods --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-change-history` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-STALE --endpoint budget-change-history --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-detail-columns` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-STALE --endpoint budget-detail-columns --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-detail-rows` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-STALE --endpoint budget-detail-rows --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-modifications` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-STALE --endpoint budget-modifications --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
- **PRJ-EMPTY** → verdict **no_data** · current 0 · stale 0 · never 56
  - no persisted procore_live_* rows for this project (never synced or unmapped)
  - stale `billing-periods` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-EMPTY --endpoint billing-periods --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-change-history` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-EMPTY --endpoint budget-change-history --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-detail-columns` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-EMPTY --endpoint budget-detail-columns --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-detail-rows` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-EMPTY --endpoint budget-detail-rows --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
  - stale `budget-modifications` (never_synced, age Noned) → HB_PROCORE_LIVE=1 hb-assistant procore live sync --project PRJ-EMPTY --endpoint budget-modifications --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json
