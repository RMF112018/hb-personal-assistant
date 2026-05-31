# 28 — Phase 07B: Data Quality Gates

Phase 07B Prompt 11. Status: implemented at this record's commit.

## Problem

The data-quality gate evaluator (`construction/data_quality/gates.py`) had two 07B stubs but:
the calendar gate **counted the non-existent `calendar_events` table** (a bug — it should be
`calendar_event_index`), so the 108 live events never registered; there were **no**
thread-summary or meeting↔email-candidate gates; and there was no authoritative 07B gate
manifest, so nothing tied the new gates to Phase 07D meeting-prep readiness.

## Change

A new authoritative manifest `resources/json/phase_07b_data_quality_gates.json`
(`phase07b-data-quality-gates-v1`) declares the four 07B presence gates (each with its V23/
V14/V11 `table`) plus the full `meeting_prep_prerequisites` list. `gates.py` now:

- Loads the manifest (`_load_phase_07b_gate_manifest()`, importlib-resources + filesystem +
  in-code fallback) in `GateEvaluator.__init__`.
- Replaces the two hardcoded 07B stubs with a single manifest-driven
  `_gate_phase_07b_presence()` — for each manifest gate, `pass` when its (trusted, in-package)
  table holds ≥1 row else `deferred_not_blocking` (`future_phase="07B"`). This **fixes the
  calendar bug** (now reads `calendar_event_index`) and **adds**
  `email_thread_summary_population_status` (`email_thread_summaries`) and
  `meeting_email_candidate_population_status` (`meeting_email_relationship_candidates`). The
  existing names (`calendar_population_status`, `email_classifier_persistence_status`) are
  preserved.
- Adds a structured `meeting_prep_readiness` block under `phase_go_nogo["07D"]`:
  `ready` is true only when **every** prerequisite (the four 07B gates + the 07C
  `document_card_population_status` + the relationship gates + the no-writeback/leakage safety
  gates) is `pass`; `blocked_by` lists the unmet ones; `auto_readiness_allowed=false` so 07D
  is never auto-claimed. The existing `meeting_prep_readiness_claim` string formula is
  unchanged (still `"blocked"` / `"needs_07b_07c_data"`, never `"ready"`).
- Extends `_CORE_GATE_NAMES` and `_PHASE_ASSIGNMENTS` with the two new 07B gate names.

No CLI change is needed — the new gates flow through `construction-agent data-quality gates`.

## Guardrail invariants
- Read-only over local read models; gates emit names/counts/statuses only (no raw values).
- The only SQLite write is the gates' own result rows via the existing
  `insert_data_quality_gate_result` (persist=True — established behavior); no external
  writeback, no Graph calls.
- **07D meeting-prep readiness stays blocked** unless all prerequisites pass;
  `auto_readiness_allowed=false`. Live, the four 07B gates pass while
  `meeting_prep_readiness.ready=false` (blocked by the 07C doc gate + a relationship gate).

## Evidence

`docs/evidence/construction-intelligence-phase-07b-calendar-email/11-data-quality-gates.json`
(commands, exit codes, and the redacted gate-name→status map + meeting-prep readiness). The
no-writeback / no-raw-body prover does not yet scan the V11/V14/V23 calendar/email tables —
deferred to Phase 07B Prompt 12.
