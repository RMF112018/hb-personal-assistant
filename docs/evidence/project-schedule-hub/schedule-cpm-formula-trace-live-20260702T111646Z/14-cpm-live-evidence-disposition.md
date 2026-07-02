# CPM Live Formula Trace Evidence Disposition

## Summary

Live CPM formula trace export completed on the same copied Tropical/TWNU cohort DB used for metric live proof. Export exit 0; lineage complete; recompute diff `pass_with_exclusions`.

## Commit-eligible artifacts

- `00-repo-state.txt`
- `02-cpm-trace-command-output.txt`
- `03-cpm-trace-exit-code.txt`
- `04-cpm-run-summary.json`
- `07-cpm-validation-recompute-diff.json`
- `08-cpm-formula-audit.md`
- `09-live-db-compare.json`
- `10-live-db-compare.md`
- `11-cpm-live-proof-summary.md`
- `12-artifact-scan.json`
- `13-artifact-scan.md`
- `14-cpm-live-evidence-disposition.md` (this file)

## Local-only artifacts

Moved to `local-sensitive/evidence/schedule-cpm-formula-trace-live-20260702T111646Z/`:

- `01-live-db-before.json` — live DB fingerprint with absolute path
- `05-cpm-activity-formula-trace.jsonl` — 1507 activity-level formula traces
- `06-cpm-relationship-formula-trace.jsonl` — 3921 relationship-level formula traces
- `cpm-formula-trace-live/` — full export directory

Rationale: activity and relationship traces contain live activity IDs, dates, float values, and relationship operands unsuitable for repo commit without operator approval.

## Safety proof

- Export read-only against git-ignored copied DB under `local-sensitive/clean-db/`.
- `09-live-db-compare.json` shows `passed: true` with zero schedule table count changes on live DB.
- No DB files staged or tracked in evidence directories.
- No raw activity/relationship trace JSONL in commit-eligible bundle.

## Remaining blockers

- Longest-path shadow recompute not implemented (documented exclusion, not a lineage failure).
- Full 14-stage clean-DB workflow not executed in this pass.
