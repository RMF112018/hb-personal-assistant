# Expected DB Invariants

- `PRAGMA integrity_check` = `ok`.
- Production DB SHA unchanged by validation.
- Guard-column sums remain zero.
- Candidate lifecycle event insertions are idempotent.
- Accepted promotion inserts exactly one row per candidate.
- Source refs remain present after accept/merge/suppress.
- Rejected/suppressed/merged items do not appear as new.
- Future snoozed items do not appear in normal views.
- Returned snoozed items appear when due.
- Source-ref-missing actionable candidates are withheld/degraded.
- Project-review-required rows remain visible.

