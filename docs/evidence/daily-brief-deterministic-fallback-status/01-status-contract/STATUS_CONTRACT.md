# Status Contract — result classes

New explicit value `deterministic_success_synthesis_degraded` (free-TEXT status; `ok=True` → exit 0).
The synthesis-degraded path no longer sets `status="partial"`; status is finalized holistically after
the usefulness gate in `run_daily_local_agent`:

| Condition (apply mode) | status |
|---|---|
| render failed / egress blocked | `failure` |
| non-synthesis pipeline stage failed | `partial` |
| usefulness gate FAILED (deterministic unusable) | `degraded` |
| usefulness PASSED + synthesis degraded + egress clean | `deterministic_success_synthesis_degraded` |
| usefulness PASSED + synthesis ok + egress clean | `success` |

`partial` (top-level boolean) now equals `status == "partial"` — the `status=partial` / `partial=false`
contradiction is removed. Dry-run keeps the existing `success` preview (no synthesis, no persisted
candidates). Status JSON + payload gain: `synthesis_status`, `synthesis_required_for_success:false`,
`deterministic_fallback{used,reason,usefulness_gate_passed,published,stable_path,counts}`,
`operator_usable`, `deterministic_fallback_used`. `run_summary.result` reports the explicit fallback
class.

## Tests

`tests/test_phase_10_deterministic_fallback_status.py` (7) — success vs fallback; no partial-false
contradiction; Option A publishing; usefulness-fail→degraded; egress-fail→failure; MEI withheld.
Updated `test_phase_10_daily_brief_correction.py::test_26_27...` to the fallback semantics. Full
targeted suite green; `ruff` clean; `mypy src` clean.
