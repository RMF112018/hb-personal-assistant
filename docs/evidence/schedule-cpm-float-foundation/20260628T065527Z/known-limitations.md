# Known limitations (by design, Phase 4)

- **Float only.** Total float + free float; nothing else.
- **No critical path, no longest path, no near-critical path. No activity is marked critical** — a zero total float is NOT criticality in this phase.
- **Depends on successful Phase 2 forward AND Phase 3 backward runs** (blocks blocked_by_missing_forward_pass / blocked_by_missing_backward_pass otherwise). Derived solely from application-owned Phase 2/3 offsets.
- **No source-field overwrite or read for logic.** Imported/source float, source early/late, source critical/driving-path flags, is_critical are never consulted; the forward/backward run rows are never mutated.
- **`cpm_recalculation_status='forward_backward_float_only'`** — never reported as a complete CPM engine. DCMA critical-path metric still returns NOT_MEASURABLE_RECALC.
- **Same simplified date/offset model as Phases 2–3** (working-day-equivalent day-offsets; no weekend/holiday/calendar engine). Negative/fractional float preserved; never clamped.
- **Inconsistent start/finish float** is flagged (inconsistent_start_finish_float) and resolved conservatively to the start-based value rather than failing.
- **No frontend/API change.** Service + repository + tests only.

## Next recommended phase
Phase 5 — Longest Path Foundation. Critical / near-critical path identification remains deferred until after longest path is implemented and validated. Sequence: P4 Float → P5 Longest Path → P6 Critical/Near-Critical → P7 DCMA Integration → P8 frontend.
