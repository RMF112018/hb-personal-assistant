# 03 — DB Copy Validation

## Source of truth

- Production DB resolved from `PathPolicy.get_db_path()` (not from memory):
  `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Size 1.95 GB. SHA-256 `a403b67b…b8a6d0`.

## Active-writer check (before copy)

- `lsof "<prod db>"` → no open handles.
- `ps aux` → the live launchd process is
  `hb-assistant scheduler run daily-source-refresh --environment dev --loop`, which writes to the
  `(Dev)` roots only. PLAIN has no writer → safe to copy and treat as frozen truth.

## Copy

```
cp "<prod db>" /tmp/hb-daily-brief-render-assembly-…/hb-render-assembly-copy.sqlite
```

- Copy SHA == source SHA at copy time (`a403b67b…b8a6d0`) → faithful copy.

## Generation on the copy (all via `--db <copy>`)

| Stage | Result |
|---|---|
| `procore-digest build --apply --max-persist 60` | persisted 50 (5933 open signals; 3817 suppressed) |
| `calendar-prep build --apply --max-persist 60 --lookahead-days 14` | persisted 45 (25 project / 18 needs-review / 2 internal-time-off) |
| `follow-up-watch scan --apply --max-persist 200` | scanned 0 (281 email summaries unconverted) |
| `synthesize-candidates --apply --max-persist 200` | persisted 0 (no accepted tasks/watch) |
| `rank-candidates --no-client --apply --max-persist 500` | 95/95 ranked, coverage 1.0, usefulness 0.9, guard_clean |
| `render --date 2026-06-12` | consumes overlay; samples 04–08 |

## Production safety

- Prod DB SHA **unchanged** before/after (see `12-prod-db-sha-unchanged.txt`).
- Pure source read-models byte-count identical prod↔copy (see `14-…-no-mutation-proof.json`).
- Guard columns sum zero across 303 tables on the copy (see `13-guard-columns-zero.json`).
- Only the V41/V51 daily-brief overlay tables (+ schema-migrations bookkeeping) changed — on the copy
  only.
