# Queried live CPM longest-path proof summary

## Conclusion: **pass**

## Copied DB proof basis

- Read-only queries against `local-sensitive/clean-db/<redacted-copy>` (not committed)
- Schema version: 98
- Schedule version: `tropical|1071|2026-06-23 08:00`
- Activities: 1507
- Relationships: 3921

## CPM lineage

- `lineage_valid`: true
- Resolution mode: `latest_terminal_criticality`
- All lineage_checks: pass (criticality→longest_path→float→backward→forward)

## Persisted longest path (queried)

- Path count: 1
- Activities on path: 45
- Relationships on path: 44
- Path duration: 429.0 days (`path_finish_offset_days - path_start_offset_days`)
- Basis: `max_forward_early_finish_backtrace`
- Terminal activity: hash `5cca4c1f4f61afb2` (redacted)

## Exporter diff (sanitized from local raw trace)

| Stage | Status |
|-------|--------|
| Overall | pass |
| forward_pass | pass |
| backward_pass | pass |
| float | pass |
| longest_path | pass |
| criticality | pass |
| source_field_exclusion | pass |

- Activity matches: 1507/1507
- Relationship matches: 3921/3921
- Path matches: 1/1

## Safety proof

- Live DB unchanged: pass (`12-live-db-compare.json`)
- Copied DB mutated: no (row-count probe before/after query export)
- Live vault write: no
- Production import: no
- DB files committed: no
- Raw traces committed: no

## Local-only evidence

`local-sensitive/evidence/schedule-cpm-longest-path-shadow-live-query-20260702T121705Z/`

- Raw exporter JSONL traces
- Live DB before snapshot (`11-live-db-before.json`)

## Remaining limitations

- Path terminal and path IDs are hash-redacted in committed evidence; full IDs exist only in local raw traces.
- Exporter diff is summarized; per-activity mismatch detail is not committed.

## Ready for full 14-stage clean-DB workflow validation

**yes** — queried evidence supports prior live longest-path shadow `pass` claims without sharing the copied DB.

## Recommended next step

Run full 14-stage clean-DB validation when operator approves; use this queried package for external review without DB upload.
