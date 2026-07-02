# CPM Live Formula Trace Summary

| Field | Value |
|-------|-------|
| Copied DB | `local-sensitive/clean-db/tropical-metric-proof-live-copy` (git-ignored backup) |
| Schedule version | `tropical\|1071\|2026-06-23 08:00` |
| Activity cohort | 1507 |
| Export exit | 0 |
| Lineage resolution | `complete` (`latest_terminal_criticality`, `lineage_valid: true`) |
| Diff status | `pass_with_exclusions` |
| Activity traces | 1507 |
| Relationship traces | 3921 |
| Matched activities | 1507 / 0 mismatches |
| Matched relationships | 3921 / 0 mismatches |
| Source-field exclusion | `pass` (no violations) |
| Longest-path shadow replay | `not_evaluated` (documented exclusion) |
| Live DB unchanged | `passed: true` |

## CPM run IDs by stage

| Stage | Run ID |
|-------|--------|
| forward_pass | `cpmrun_473bef89651e3378b693abe00c0edc9a` |
| backward_pass | `cpmrun_28633bd2f97bb45bdd2d4e0bf76cf3cb` |
| float | `cpmrun_8fe50672cff7dbb84a96edb5f62c393b` |
| longest_path | `cpmrun_a7128b38ab1ddc6d3a749cae6057ac64` |
| criticality (terminal) | `cpmrun_97aa5bebc8ead974c0667e1ed2c4de25` |

## Limitations

- Longest-path independent shadow replay is not implemented; path export is persisted-only.
- Full activity/relationship formula trace JSONL remains local-only (live schedule operational detail).
- This pass does not substitute for the full 14-stage clean-DB validation workflow.
