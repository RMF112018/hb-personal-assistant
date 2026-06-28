# Known limitations (by design, Phase 3)

- **Backward pass only.** Late start / late finish; no float of any kind (total/free/interfering/independent), no longest path, no critical path.
- **Depends on a successful Phase 2 forward-pass run** for the same schedule version (blocks `blocked_by_missing_forward_pass` if absent).
- **No source-field overwrite or read for logic.** Finish anchor reads imported `finish_date`/`planned_finish` only — never source `early_finish`/`late_finish`/float/critical/driving-path flags. The forward-pass run's rows are never mutated.
- **`cpm_recalculation_status='backward_pass_only'`** — never reported as a complete CPM engine. DCMA critical-path metric still returns NOT_MEASURABLE_RECALC.
- **Same simplified date model as Phase 2.** Working-day-equivalent day-offsets from the start anchor are authoritative; ISO datetimes use calendar-day arithmetic; NO weekend/holiday/calendar engine. Finish anchor is an offset in that same space.
- **Finish anchor earlier than the forward-pass finish is allowed** (records caveat `finish_anchor_before_forward_pass_finish`, may yield negative offsets) — not failed. This occurs with the minimal.xer fixture (imported finish precedes its data date).
- **No frontend/API change.** Service + repository + tests only.

## Next recommended phase
Phase 4: total float (= late − early, both already computed) with explicit float-basis provenance — still source-field-preserving; then critical/longest-path identification as a later phase.
