# Live Metric Formula Proof Evidence Disposition

## Summary

| Field | Value |
|-------|-------|
| Copied DB | `local-sensitive/clean-db/tropical-metric-proof-live-copy` (git-ignored backup) |
| Requested schedule version | `tropical\|TWNU19\|2026-06-23T08:00:00` |
| Resolved schedule version | `tropical\|1071\|2026-06-23 08:00` |
| Activity cohort | 1507 activities |
| Export exit | 0 |
| Shadow recompute | `pass_fixture` (3/3 traces matched) |
| Live DB unchanged | `passed: true` (`02-live-db-compare.json`) |
| Artifact scan (sanitized bundle) | passed (0 findings) |

## Commit-eligible artifacts

PM-safe summaries without raw live schedule rows:

- `02-live-db-compare.json`
- `03-live-db-compare.md`
- `04-artifact-scan.json`
- `05-artifact-scan.md`
- `06-live-proof-summary.md`
- `10-metric-api-activation-proof.json`
- `11-metric-independent-recompute-diff.json`
- `12-metric-proof-audit.md`
- `13-live-evidence-disposition.md` (this file)

## Local-only artifacts

Moved to `local-sensitive/evidence/schedule-metric-formula-proof-live-20260702T110535Z/`:

- `00-live-db-before.json` — live DB path and table-count fingerprint
- `01-live-export-command.txt` — operator command log with paths
- `07-metric-formula-registry.json` — duplicate of committed registry (not required in live bundle)
- `08-metric-input-snapshot.json` — full live activity/CPM input rows
- `09-metric-computation-trace.jsonl` — trace-level operands on live data
- `metric-formula-proof-live/` — full export directory including input snapshot and traces

Rationale: input snapshots and computation traces contain live project activity IDs, dates, durations, WBS paths, and operational schedule fields unsuitable for repo commit without operator approval.

## Safety proof

- Live DB was read-only snapshotted; export ran against sqlite `.backup` copy only.
- `02-live-db-compare.json` shows zero schedule table count changes.
- No DB files under `docs/evidence/` or staged for commit.
- No raw live trace JSONL or input snapshots remain in the commit-eligible evidence directory.

## Remaining live-proof limitations

- Health/feasibility composites: `pass_with_policy_limitations` (weights not business-validated).
- UDF-dependent metrics may be `not_computable_missing_udf` where normalization absent.
- Near-critical delta requires paired prior/current CPM runs.
- Baseline delay requires selected baseline state.
- Shadow evaluator covers subset of metrics (progress count, SPI duration, critical indices).
