# 03 — Gate Follow-Up Watch Persistence on Quality Flags

## Goal
Make `run_follow_up_watch_scan` persistence consistent with the follow-up watch *report* quality
gates. Previously the scan/persist path gated only on source refs, so a source-linked but
**contradictory** item (terminal status + active waiting_state + no completion) could persist as
actionable watch state even though the report routes it to `needs_review`.

## Change (`local_ai/follow_up_watch.py`, `run_follow_up_watch_scan`)
- Added summary counter `skipped_quality_flags` (init 0).
- After the source-ref gate passes (so `has_source_ref=True`), compute
  `watch_quality_flags(status, waiting_state, completed_utc, has_source_ref=True)`. If non-empty:
  do **not** persist; increment `skipped_quality_flags`; set `quality_flags` +
  `skipped_reason="quality_flags"` on the result entry; continue.
- Added guardrail `quality_gated: True`.
- No schema change. Missing-source-ref and unchanged-status skips are unchanged. Dry-run behavior
  unchanged except the new counter/metadata.

## Proof (disposable temp DB — `quality-gate-persistence-proof.json` / `final-output.json`)
Seeded one **contradictory** source-linked task ('contra') and one **clean** control
('clean', waiting_on_me/open):
- scanned: 2
- skipped_quality_flags: 1 (the contradictory item)
- persisted: 1 (only the clean control)
- status_events_written: 1 (only the clean control)
- contradictory entry: `quality_flags=["contradictory"]`, `skipped_reason="quality_flags"`, not persisted
- watch table after apply: 1 row (`watch:acc-task:clean`); contradictory NOT persisted
- guard / table counts confirm only the legitimate item was written.

The control proves the gate is **selective** (it blocks flagged items, not all items).

## Test
`tests/test_phase_10_follow_up_watch_report.py::test_scan_does_not_persist_quality_flagged_items`.
Existing tests remain green.
