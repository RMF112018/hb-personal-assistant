Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 04 — Daily-Run Default-On Integration

## Objective

Make Model Enriched Intelligence default-on for daily-run and scheduled runs while preserving explicit operator disable and deterministic fallback.

## Required CLI behavior

`hb-assistant second-brain daily-run run` must default to:

- Model Enriched Intelligence enabled
- browser generation enabled unless explicitly disabled
- browser auto-open disabled
- raw-enrichment readiness checked
- no persistence in dry-run
- capped persistence in apply

Add or normalize flags:

- `--model-enriched-intelligence`
- `--no-model-enriched-intelligence`

If old flags exist, preserve aliases and update help text.

## Required scheduler behavior

Scheduler install preview and generated ProgramArguments must include default-on model-enriched posture. If the flag defaults on without an explicit arg, status must still show the effective value.

Scheduler must not auto-open browser.

## Required status behavior

Daily-run status summary must show:

- Model Enriched Intelligence enabled/disabled
- available/degraded/withheld
- source-linked bullet counts
- pending email enrichment counts
- browser latest path
- last successful path
- failure/partial reason

## Evidence

Update/create:

- `08-status-json-proof.json`
- `09-scheduler-install-preview-proof.json`
- `15-daily-run-integrated-proof.json`
- `22-cli-help-snapshots.md`

## Tests

Add tests for:

- daily-run default-on
- disable flag
- scheduler ProgramArguments / effective config
- status summary includes model-enriched posture
