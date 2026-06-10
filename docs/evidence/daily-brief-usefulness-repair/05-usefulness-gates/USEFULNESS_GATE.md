# Priority 5 — Usefulness / Success Gates + Surface Integration (Prompt 05)

## What changed

- **New** `src/hb_assistant/construction/second_brain/local_ai/usefulness_gate.py`:
  `evaluate_usefulness_gate(store, brief_date, *, synthesis_present, synthesis_degraded,
  egress_clean=True)` → `UsefulnessGateResult(passed, verdict, failed_reasons, metrics)`.
  Metrics: deterministic_section_count, calendar_project_resolution_rate,
  calendar_unresolved_project_like_count, procore_executive_count,
  procore_aggregate_sludge_selected (0 by construction — sludge is demoted, never persisted),
  source_ref_coverage, executive_source_ref_coverage, synthesis present/degraded, contradiction flag,
  egress_clean, per-section counts.
  - **`success` bar**: ≥1 useful deterministic section; no synthesis/deterministic contradiction;
    100% executive source-ref coverage; project-like calendar not all unresolved; Procore top rows
    not aggregate sludge; clean egress. Internal (PTO/training/company) calendar events are NOT
    project-like, so an all-internal calendar does not trip the unresolved check.
- **Integrated into** `daily_run.run_daily_local_agent`: the gate runs after deterministic projection
  + synthesis and before `is_fresh_success`. An apply-mode `success` that fails the gate is downgraded
  to `partial` with a `usefulness_gate_failed: <reasons>` warning. Because `is_fresh_success` requires
  `status == "success"`, the downgrade **prevents `daily-brief-latest.html` overwrite and the
  last-successful pointer update** — the last good brief is preserved. Dry-run previews are left
  unchanged (they never persist candidates and are never a fresh success).
- **Status JSON + payload**: both now carry a `usefulness_gate` block (verdict + failed_reasons +
  metrics). The `usefulness_gate_failed` reason is surfaced in `warnings` (rendered in browser/Obsidian
  output, alongside the existing degraded-synthesis banner).

## Tests

- `tests/test_phase_10_usefulness_gate.py` — 7 passed:
  - useful run passes; empty sections degraded; zero source-ref coverage degraded; all-calendar
    unresolved degraded; synthesis-without-candidates contradiction degraded; internal-only calendar
    does not trip the unresolved check; **integration**: an apply run with an unresolved project-like
    meeting downgrades to `partial`, writes no `browser_latest_path`, creates no `last-successful.json`,
    and the status JSON `usefulness_gate.verdict == "degraded"`.
- Full targeted suite (`test_phase_10_daily_run*`, `test_phase_10_daily_brief*`,
  `test_phase_10_procore*`, `test_phase_10_calendar*`) — **208 passed**.
- `ruff check` on changed files: clean.
