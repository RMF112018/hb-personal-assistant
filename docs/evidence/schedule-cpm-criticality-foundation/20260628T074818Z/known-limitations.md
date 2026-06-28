# Known limitations (by design, Phase 6)

- **Computed criticality classification only** — NOT DCMA critical-path compliance and NOT a near-critical PATH (per-activity classification from total float).
- **No DCMA critical-path metric integration or relabel** (stays NOT_MEASURABLE_RECALC; deferred to Phase 7).
- **No frontend/API change** (deferred to Phase 8).
- **No source-field overwrite or reinterpretation.** Source critical/driving-path/float/early/late and is_critical are never computation inputs and never carried into criticality rows (explicit app-owned whitelist; is_critical never mutated).
- **Longest-path membership is contextual**, never overriding the total-float classification.
- **Depends on successful Phase 4 float AND Phase 5 longest-path runs** (blocks blocked_by_missing_float_run / blocked_by_missing_longest_path_run; invalid thresholds block invalid_criticality_thresholds).
- **`cpm_recalculation_status='criticality_classification_only'`** — never a complete CPM engine.
- **Negative float classifies critical, never clamped.** Same simplified offset model as Phases 2–5 (no calendar engine).

## Next recommended phase
Phase 7 — DCMA Critical Path Metric Integration (reconcile computed criticality/longest-path with the DCMA critical-path metric). Sequence: P4 Float → P5 Longest Path → P6 Critical/Near-Critical → P7 DCMA Integration → P8 frontend.
