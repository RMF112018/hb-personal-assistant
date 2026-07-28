# Phase D failed run 003 — root-scoped FTS join order

Disposition: preserved failure; superseded only by a later passing exact-candidate rehearsal

## Observed result

Two complete 100,000-file canaries passed fresh scan, no-change, 0.1%/1%/10% deltas, WAL checkpoint,
bounded write-lock failure, and recovery. Both failed the search criteria:

- cold fresh-connection search: approximately 1.78–1.84 seconds;
- warm p95: approximately 1.94–2.05 seconds (SLO: 250 ms);
- four-client concurrent p95: approximately 11.22–11.89 seconds (SLO: 1,000 ms);
- search errors: zero.

The failure was therefore latency/plan selection, not correctness or connection safety.

## Root cause and exact plan evidence

On the retained 100,000-row diagnostic database, SQLite reordered the ordinary inner joins and started at
the root-scoped locator index:

```text
SEARCH l USING INDEX idx_locators_reconcile (source_root_key=?)
SEARCH s USING source_entity_id
SEARCH m USING source_entity_id
SCAN f VIRTUAL TABLE
```

The engine consequently probed the FTS virtual table once per root locator. Direct measurements of the
current query were 2,771.111 ms, 1,780.785 ms, and 1,761.855 ms for the selective single-result token.

## Corrective action

The two external-source FTS methods now use intentional `CROSS JOIN` ordering:

```text
FTS virtual-table match
  -> idx_si_metadata_fts_rowid
  -> source entity primary key
  -> current locator by entity
```

The same populated-database query under this order measured 0.644 ms, 0.101 ms, and 0.069 ms. An exact
query-plan regression test requires the FTS virtual table as the first loop, requires
`idx_si_metadata_fts_rowid`, and rejects a locator scan.
