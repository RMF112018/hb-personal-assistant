# 21 — Validation Results

Branch: `experiment/phase-10-top3-local-model-agent-convergence` (base `ebd8e74a`).
Toolchain: `.venv` Python 3.12. Ollama reachable locally (real probes succeed); all tests use injected
offline backends so they are hermetic and do not depend on live inference.

## Targeted tests (new) — 30 passed

```
tests/test_phase_10_daily_brief_intelligence_convergence.py    5 passed
tests/test_phase_10_model_enriched_intelligence_render.py      6 passed
tests/test_phase_10_daily_run_scheduler_hardening.py           5 passed
tests/test_phase_10_email_raw_enrichment_readiness.py          8 passed
tests/test_phase_10_email_raw_enrichment_pipeline.py           5 passed
tests/test_phase_10_top3_daily_run_integration.py              1 passed
```

## Regression (existing, touched areas) — passed

```
test_phase_10_daily_run.py, _daily_run_reliability.py, _daily_run_pending_followup_convergence.py,
_daily_brief_rendering.py, _pipeline.py, _email_followup_cli.py, _email_followup_engine.py,
_email_followup_daily_brief.py, test_launchd_scheduler_agent.py, test_daily_brief_intelligence.py
```

No failures attributable to this package.

## Lint / type / compile (changed modules)

- `ruff check` (changed src + new tests): All checks passed.
- `mypy` (changed src modules): Success, no issues.
- `python -m compileall`: OK.

## CLI smoke

- `second-brain daily-run run` (default) → JSON `model_enriched_intelligence.enabled=true`, label exact.
- `--no-model-enriched-intelligence` → `enabled=false`, `withheld_reason="disabled"`.
- `--no-email-raw-enrichment` honored (no flag collision after fixing the alias negative token).
- `second-brain follow-up-watch enrich-readiness --json` → raw-free funnel report.
- `second-brain daily-run scheduler install --dry-run` → ProgramArguments include
  `--model-enriched-intelligence`, `--email-raw-enrichment`, `--no-open-browser`; grammar valid.

## DB-copy live proof (seeded-copy, production untouched)

- Production DB sha256 unchanged before/after (`20`).
- Capped apply respected (cap=2 over 3 eligible → persisted 2); idempotent rerun added 0 (`13`,`14`).
- Integrated daily-run apply: MEI available, consumed pending rows, egress clean (`15`).
- Model-unavailable: MEI withheld+degraded, deterministic brief preserved, run still rendered (`16`).
- V45 guard columns all zero (`19`). Evidence forbidden-string scan CLEAN (`17`).
