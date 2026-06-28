# Known limitations (by design, Phase 7)

- **No frontend/storytelling** (deferred to Phase 8 CPM API / Frontend Surfacing).
- **No source critical/driving-path reinterpretation.** Source is_critical/driving-path/float and imported early/late are never computation inputs; is_critical is never mutated. XER/MSP source criticality is never treated as a DCMA-computed critical path.
- **No automatic CPM recomputation inside the quality evaluator.** The evaluator only READS the latest CPM runs; it never creates or writes CPM runs.
- **Conservative measurability.** The DCMA critical-path metric is measurable only when every dependency run is successful, the longest path passes integrity checks, and every longest-path activity is computed_critical. Any missing/blocked/inconsistent dependency keeps it not measurable with explicit reasons.
- **No DCMA certification claim** beyond the implemented metric evidence (basis application_computed_cpm + dependency run ids).
- **Calendar limitations inherited** from prior CPM phases (working-day-equivalent day-offsets; no weekend/holiday/calendar engine).
- **Source-export + supplemental proxy metrics preserved unchanged and separate.**

## Pre-existing (not introduced by this phase)
tests/test_schedule_quality_api.py::test_twnu_quality_scorecard_when_zip_present[TWNU07/16/18.xml] fail on the Phase 6 baseline too (CPLI status expectation under real TWNU zip fixtures) — unrelated to this change and not part of the schedule bundle.

## Next recommended phase
Phase 8 — CPM API / Frontend Surfacing Foundation (expose computed CPM chain + DCMA integration evidence + provenance). PM-facing storytelling remains a later phase unless authorized.
