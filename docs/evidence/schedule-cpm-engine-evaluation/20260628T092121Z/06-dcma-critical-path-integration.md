# 06 — DCMA Critical Path Metric Integration

## What this metric is (and is not)

The DCMA critical-path metric is made **measurable only when a valid, internally consistent
application-computed CPM chain exists**. It is **evidence-based**, not a certification. This
package does **not** claim "certified DCMA compliant" or a "true / P6 critical path."

## Behavior matrix

| Condition | Behavior |
| --- | --- |
| Source-only schedule (no computed CPM attempted) | `not_measurable_requires_recalculation` — preserved source-only behavior |
| CPM attempted but incomplete / inconsistent | evaluation returned with `reason_codes` explaining why it is not measurable |
| Valid, consistent computed CPM chain | **measurable**, status `available_app_cpm_recalculated`, basis `application_computed_cpm` |
| Missing dependency run | reflected in `missing_dependency_reasons` / `reason_codes` |

The pure evaluator (`evaluate_dcma_critical_path_eligibility`) decides measurability from:
dependency presence/success, graph-fatal state, longest-path integrity, and criticality
consistency. The service method `ScheduleCpmGraphService.evaluate_dcma_critical_path(svk)` reads
the latest runs and returns `None` when none were attempted (so source-only behavior is
preserved), or an evaluation when attempted.

## Evaluated result (this schedule)

From `artifacts/dcma-computed-cpm-sample.json` (structured) and the embedded `dcma_critical_path`
block in `artifacts/api-cpm-summary-sample.json`:

```json
{
  "measurable": true,
  "basis": "application_computed_cpm",
  "reason_codes": [],
  "caveats": ["computed_critical_outside_longest_path"],
  "dependency_run_ids": {
    "forward": "cpmrun_e30f127db1e1d89c67263e64e753475c",
    "backward": "cpmrun_e7e97b3eeb44c400f18cb89af6766de9",
    "float": "cpmrun_d32e29265538e09d6d066589ea10a7cf",
    "longest_path": "cpmrun_17f1ffb7fe59a4e341a046262ea2dee9",
    "criticality": "cpmrun_7c4d330eba04db4a18756bde0c0dd9fc"
  },
  "path_id": "cpmrun_17f1ffb7fe59a4e341a046262ea2dee9_p01",
  "path_activity_count": 45,
  "computed_critical_activity_count": 1312,
  "longest_path_critical_activity_count": 45,
  "evidence": {
    "source_critical_flags_used": false,
    "source_export_evidence": "separate"
  }
}
```

### Key facts

- **Status:** `available_app_cpm_recalculated` (the v89-added measured status), measurable = true.
- **Basis:** `application_computed_cpm`.
- **Dependency run IDs:** the five chain runs (forward, backward, float, longest_path, criticality)
  are all present — path integrity and criticality consistency satisfied.
- **Path:** `..._p01` with **45** activities; longest-path-critical count = 45.
- **`source_critical_flags_used: false`** — source critical flags played no part.

## Caveat carried forward: `computed_critical_outside_longest_path`

The computed criticality classification marks **1312** activities critical, while the longest
path itself contains **45** activities (`computed_critical_activity_count` 1312 vs
`longest_path_critical_activity_count` 45). The engine flags this divergence with the caveat
**`computed_critical_outside_longest_path`** rather than silently reconciling it: many activities
classed "critical" by the criticality run lie **outside** the single extracted longest path
(expected with parallel near-zero-float chains). This caveat must be carried into any Phase 9
narrative language and must not be presented as a single "the critical path is 1312 activities"
claim.

## Artifact references

- `artifacts/dcma-computed-cpm-sample.json` (structured JSON; `measurable: true`)
- `artifacts/capture-dcma-sample-structured.py` / `artifacts/capture-dcma-sample-output.txt`
- `artifacts/api-cpm-summary-sample.json` (embedded `dcma_critical_path` block)
