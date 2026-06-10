# 06 — Idempotency and precedence

Operation sequence on one `prime-change-orders` record
(`test_source_quality_rank_upgrade_and_idempotency`,
`test_legacy_replay_cannot_overwrite_or_downgrade_full_rows`):

| # | operation | raw rows (persisted=1) | structured rows | structured source_quality | amount | skipped_due_to_higher_quality | verdict |
|---|---|---:|---:|---|---|---:|---|
| 1 | legacy backfill | 0 | 1 | redacted_legacy_projection | NULL | 0 | degraded baseline |
| 2 | full upsert | 1 | 1 | live_full_payload | 491383.15 | 0 | UPGRADE in place |
| 3 | full upsert (re-run) | 1 | 1 | live_full_payload | 491383.15 | 0 | IDEMPOTENT (no dup) |
| 4 | fixture_full upsert (rank 90) | 1 | 1 | live_full_payload | 491383.15 | 1 | NO DOWNGRADE (skipped) |
| 5 | legacy backfill (after full) | 1 | 1 | live_full_payload | 491383.15 | 1 | NO OVERWRITE (skipped) |

## Source-quality distribution observations

- Step 2 upgrades the structured row in place (single `record_key`); the legacy
  structured row is replaced, not duplicated.
- Step 3 (full twice): `COUNT(*) procore_raw_change_orders = 1`,
  `COUNT(*) raw persisted=1 = 1` — idempotent.
- Step 4: a lower-rank `fixture_full_payload` write is skipped; `amount` unchanged.
- Step 5: legacy replay for the same identity reports `skipped_due_to_higher_quality=1`,
  writes 0 raw + 0 structured; the full row's `source_quality`, `amount`, `owner_name`,
  and `status` are unchanged (legacy `status="closed"` never overwrote full `status="open"`).

## Downgrade-prevention guarantee

A lower-rank write (legacy or fixture) can never overwrite or downgrade a higher-rank
row — enforced at the structured `record_key` (rank compare) and, for legacy replay,
additionally at the raw-payload identity (`_existing_raw_full_rank >= fixture_full`).
