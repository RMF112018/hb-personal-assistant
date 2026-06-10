Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 05 — Scheduler Live Hardening and Status

## Objective

Make scheduler install/status/readiness robust enough that the daily brief can reliably appear at 5:00 AM or next machine wake, with clear local diagnostics.

## Required audit

Inspect `daily_run_scheduler.py`, `cli/second_brain.py`, and any scheduler CLI modules.

## Required implementation

Enhance scheduler status/install preview to report:

- plist path redacted
- plist exists
- executable path and readiness
- working directory readiness
- log directory readiness
- command grammar valid
- schedule time local
- weekday intervals
- catch-up-on-wake explanation
- timezone
- DB path redacted if set
- vault brief dir redacted
- browser output dir redacted if set
- Model Enriched Intelligence effective enabled/disabled
- email raw enrichment effective enabled/disabled
- browser generation enabled
- browser auto-open false
- latest status path
- last successful brief path if known
- last run result if known
- blocking diagnostics

If a launchd command cannot be safely executed during tests, provide dry-run/status proof rather than mutating operator launch agents.

## Required live/local proof

On Bobby's machine, when safe:

1. Run install preview.
2. Run status.
3. Run a manual daily-run dry-run.
4. Run a manual daily-run apply on a DB copy.
5. Verify status files and output paths.
6. Do not auto-open browser.

## Evidence

Create:

- `09-scheduler-install-preview-proof.json`
- `10-scheduler-status-proof.json`
- `23-output-path-safety-proof.md`

## Tests

Add tests for:

- readiness fields
- redacted paths
- no browser auto-open
- blocking diagnostic if executable/log/workdir invalid
- launchd ProgramArguments include/convey effective defaults
