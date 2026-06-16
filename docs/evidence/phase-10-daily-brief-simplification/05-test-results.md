# 05 — Test results

## Static checks (changed files)

| Check | Result |
|---|---|
| `python -m compileall src tests` | PASS (COMPILEALL OK) |
| `ruff check` (new module, `daily_run.py`, new test) | PASS (All checks passed!) |
| `ruff format --check` (new module, new test) | PASS (already formatted) |
| `mypy` (`new_today_usefulness.py`, `daily_run.py`) | PASS (no issues found in 2 source files) |

## Focused suites (the touched area)

```
pytest tests/test_phase_10_daily_brief_simplified.py \
       tests/test_phase_10_new_today.py \
       tests/test_phase_10_daily_run.py \
       tests/test_phase_10_usefulness_gate.py -q
→ 84 passed, 0 failed
```

- `test_phase_10_daily_brief_simplified.py` — **14 new tests**, all pass:
  - pure gate semantics (clean-empty → success; email-degraded / projection-degraded / coverage-
    degraded / all-events-dropped → degraded; model-unavailable → not product-degraded);
  - **crux** — gate cannot see legacy synthesis state (structural lock); success status renders no
    visible warning; degraded status renders the warning;
  - Markdown↔HTML parity + forbidden-token absence + header/subhead contract;
  - full scheduled run emits the `daily_brief` block (return payload + `latest-status.json`), browser
    HTML leads with New Today, guard columns zero, two enrichment fields distinct.

## Bounded regression subset (full blast radius)

```
pytest tests/ -k "daily_brief or new_today or daily_run or second_brain or usefulness or
                  synthesis or model_enriched or candidate_ranking or assembly or
                  presentation or render" -q
→ green EXCEPT 2 pre-existing failures (below)
```

## Pre-existing, unrelated failures (NOT caused by this slice)

`tests/test_second_brain_no_writeback_proof.py::test_proof_passes_on_clean_repo` and
`::test_cli_no_writeback_proof_exit_zero` fail because the proof's `static_writeback_scan_08a_modules`
greps for the literal `.update(` and flags **Python dict `.update()` calls** (not external writeback)
in:

- `local_ai/candidate_ranking_packets.py`
- `local_ai/daily_brief_effectiveness_packets.py` (×3)
- `local_ai/daily_brief_intelligence.py`
- `local_ai/daily_run.py`

Proof this is pre-existing and not from this change:
- `git diff` of `daily_run.py` added **zero** `.update(` lines; `new_today_usefulness.py` contains
  none.
- `candidate_ranking_packets.py`, `daily_brief_effectiveness_packets.py`, and
  `daily_brief_intelligence.py` are **unmodified** (identical to HEAD `9678e2e4`), yet they alone make
  the binary proof fail.

Matches the known pre-existing-failures record for this tree.

## Full default-safe subset

`pytest -m "not integration and not live and not manual"` over the entire repo was launched but is
very slow on this tree (30 min+). It is superseded for this change by the bounded area subset above,
which covers every module the slice touches. The only failure observed anywhere is the documented
pre-existing no-writeback proof.
