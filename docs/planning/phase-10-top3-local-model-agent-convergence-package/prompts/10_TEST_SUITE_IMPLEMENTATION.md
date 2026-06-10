Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 10 — Test Suite Implementation

## Objective

Add a complete targeted test suite covering all three candidates and their integration.

## Required test groups

### Daily Brief Intelligence / Synthesis Convergence

- default-on daily-run
- disable flag
- source-linked bullets survive
- unknown source IDs dropped
- no source-linked bullets withheld
- model unavailable fallback
- schema invalid fallback
- exact label: `Model Enriched Intelligence`
- status JSON raw-free
- browser/Obsidian raw-free

### Scheduler / Daily-Run Live Hardening

- install preview includes effective defaults
- status includes readiness fields
- ProgramArguments grammar valid
- browser auto-open false
- output path guards reject repo-contained paths
- last successful pointer preserved on failure/partial

### Email Follow-Up Raw Enrichment Productionization

- eligibility no-op reasons
- dry-run no persistence
- apply requires cap
- cap respected
- idempotency
- source-link required
- local model unavailable skip/degrade
- raw policy disabled skip/degrade
- pending rows consumed by Model Enriched Intelligence

### Cross-candidate integration

- one daily-run receipt shows:
  - email raw enrichment stage
  - model enriched intelligence stage
  - render stage
  - scheduler-compatible status block
- no raw content in any output
- guard columns zero
- production DB untouched in proof path

## Required validation commands

Run targeted tests first. Then run changed-module lint/type/compile.

Suggested:

```bash
python -m pytest -q \
  tests/test_phase_10_daily_brief_intelligence_convergence.py \
  tests/test_phase_10_model_enriched_intelligence_render.py \
  tests/test_phase_10_daily_run_scheduler_hardening.py \
  tests/test_phase_10_email_raw_enrichment_readiness.py \
  tests/test_phase_10_email_raw_enrichment_pipeline.py \
  tests/test_phase_10_top3_daily_run_integration.py

python -m compileall src tests
ruff check <changed files>
mypy <changed src files>
```

If broad test suites fail, prove whether failures are pre-existing. Do not hide failures.

## Evidence

Create:

- `21-validation-results.md`
