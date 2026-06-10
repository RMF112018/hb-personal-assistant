Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 09 — CLI Operator Surface Consolidation

## Objective

Make the operator CLI clear enough that Bobby can run, inspect, troubleshoot, disable, and validate all three candidates without reading code.

## Required commands/help

Audit and update help for:

- `second-brain daily-run run`
- `second-brain daily-run scheduler install`
- `second-brain daily-run scheduler status`
- `second-brain follow-up-watch enrich`
- new/enhanced `second-brain follow-up-watch enrich-readiness`
- `second-brain daily-brief intelligence`
- `second-brain local-model route`
- `second-brain local-model diagnostics`

## Help text requirements

Help must state:

- Model Enriched Intelligence is default-on.
- Use `--no-model-enriched-intelligence` to disable.
- Browser auto-open is disabled.
- Email raw enrichment is local-only, bounded, review-safe, and source-linked.
- Raw preview, if present, is terminal-only, dry-run only, and never JSON/apply.
- Apply requires caps.
- DB-copy validation is recommended.

## Required output modes

For relevant commands:

- `--json` default where repo convention expects it.
- `--no-json` / markdown output where repo convention supports it.
- `--markdown-out` if existing pattern supports it.
- exit codes consistent with existing conventions:
  - success when deterministic fallback safely renders
  - nonzero or explicit degraded/blocked when requested unsafe/unsupported action fails closed

## Evidence

Create:

- `22-cli-help-snapshots.md`

## Tests

Add CLI runner tests for:

- help text contains exact label
- default-on reflected in JSON
- disable flag reflected in JSON
- raw preview refused with JSON/apply
- readiness command raw-free
