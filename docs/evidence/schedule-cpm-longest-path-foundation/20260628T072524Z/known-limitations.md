# Known limitations (by design, Phase 5)

- **Longest path only** — a longest-path BASIS, not a critical-path declaration.
- **No critical path, no near-critical path, no float threshold, no critical marking, no `is_critical`.** The longest path is never labeled the critical path.
- **Depends on successful Phase 2 forward AND Phase 4 float runs** (blocks blocked_by_missing_forward_pass / blocked_by_missing_float_run otherwise). Derived solely from application-owned Phase 2/3/4 results, read through the float run.
- **No source-field overwrite or read for logic.** Imported/source critical/driving-path/float/early/late fields are never consulted; prior CPM run rows are never mutated.
- **`cpm_recalculation_status='longest_path_only'`** — never a complete CPM engine; DCMA critical-path metric unchanged (NOT_MEASURABLE_RECALC).
- **Single primary path (path_rank=1).** No alternate/secondary paths enumerated in this phase.
- **Conservative degradation:** unsupported/unreconstructable backtrace cases stop with a degraded status and a partial persisted chain rather than fabricating a controlling predecessor.
- **Same simplified offset model as Phases 2–4** (working-day-equivalent day-offsets; no weekend/holiday/calendar engine).
- **No frontend/API change.**

## Next recommended phase
Phase 6 — Critical / Near-Critical Path Foundation (total-float threshold over the computed float + this longest path). Sequence: P4 Float → P5 Longest Path → P6 Critical/Near-Critical → P7 DCMA Integration → P8 frontend. DCMA metric stays NOT_MEASURABLE_RECALC until Phase 7.
