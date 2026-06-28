# 04 — CPM Computation Chain

Evaluated schedule version: **`tropical|1071|2026-06-23 08:00`** (TWNU19, primavera_xer,
1507 activities / 3921 relationships / 215 WBS).

## Chain stages

| # | Stage | Input | Output | Run status observed | Computed activities |
| --- | --- | --- | --- | --- | --- |
| 1 | Graph diagnostics | source activities + relationships | `schedule_cpm_diagnostics`, run row | `not_implemented` | 0 |
| 2 | Forward pass | graph | `schedule_cpm_activity_results` (early dates) | `forward_pass_only` | 1507 |
| 3 | Backward pass | forward results | activity results (late dates) | `backward_pass_only` | 1507 |
| 4 | Float | forward + backward | activity results (total/free float) | `forward_backward_float_only` | 1507 |
| 5 | Longest path | float results | `schedule_cpm_paths`, `schedule_cpm_path_activities` | `longest_path_only` | 0 (path-level output) |
| 6 | Criticality | longest path + float | activity results (criticality class) | `criticality_classification_only` | 1507 |
| 7 | DCMA critical-path integration | runs 2–6 | `DcmaCriticalPathEvaluation` (read-time) | `measurable=true` | n/a (evaluation) |
| 8 | API / frontend surfacing | persisted runs | JSON responses + Computed CPM page | read-only | n/a |

Graph metrics are constant across runs: `node_count=1507`, `edge_count=3921`,
`diagnostic_count=52`, `is_acyclic=1`. Source: `artifacts/cpm-run-verification.txt`.

## Run IDs (dependency chain)

| Stage | `cpm_run_id` | `source_run_id` |
| --- | --- | --- |
| graph_diagnostics | `cpmrun_97791f323c76a1b02a23f7f638a0779b` | (none) |
| forward_pass | `cpmrun_e30f127db1e1d89c67263e64e753475c` | (none) |
| backward_pass | `cpmrun_e7e97b3eeb44c400f18cb89af6766de9` | (none) |
| float | `cpmrun_d32e29265538e09d6d066589ea10a7cf` | `...e7e97b...` (backward) |
| longest_path | `cpmrun_17f1ffb7fe59a4e341a046262ea2dee9` | `...d32e29...` (float) |
| criticality | `cpmrun_7c4d330eba04db4a18756bde0c0dd9fc` | `...17f1ff...` (longest_path) |

(The DCMA evaluation references the forward/backward/float/longest_path/criticality run IDs as
its dependency set — see doc 06 and `artifacts/dcma-computed-cpm-sample.json`.)

## Run timestamps

All six runs persisted within the same execution window: `graph_diagnostics`, `forward_pass`,
`backward_pass` at `2026-06-28 09:55:16`; `float`, `longest_path`, `criticality` at
`2026-06-28 09:55:17` (`artifacts/cpm-run-verification.txt`).

## Caveats

- **`graph_diagnostics` reports `cpm_recalculation_status = not_implemented`** with
  `computed_activity_count = 0`. This is the **diagnostics-only** scope (it inventories the
  graph: 52 diagnostics, acyclic) — it is **not** a CPM computation failure. The status **label**
  `not_implemented` is easy to misread in an executive context and is flagged for review (docs
  00 / 11 / 12).
- `longest_path` shows `computed_activity_count = 0` at the run-summary level because its output
  is **path-level** (`schedule_cpm_paths` / `schedule_cpm_path_activities`), not per-activity
  rows; the longest path contains **45 activities** (doc 06 / `artifacts/cpm-longest-path-sample.json`).
- The DCMA evaluation carries the caveat `computed_critical_outside_longest_path` (doc 06).

## Artifact references

- `artifacts/cpm-chain-run-output.json`
- `artifacts/cpm-chain-run-output.txt`
- `artifacts/cpm-run-verification.txt`
- `artifacts/cpm-run-samples.json`
- `artifacts/cpm-activity-samples.json`
- `artifacts/cpm-longest-path-sample.json`
- `artifacts/cpm-criticality-sample.json`
- `artifacts/run-cpm-chain-for-imports.py` (chain runner used to populate the evidence DB)
