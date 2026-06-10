# Evidence — 05 Local Model Routing Refinement

Candidate: `local-model-routing-refinement` · Prompt: `prompts/05_local_model_routing_refinement.md`
Branch: `experiment/phase-10-full-candidate-implementation` · Baseline: `0c75f4a7…`

## Scope

Added a consolidated **routing diagnostics** surface (`local-model diagnostics`) that sweeps every
Phase 10 task family and reports selected profile, candidate model chain, probe/availability status,
fallback reason, fail-closed reason, and a declared output safety category — deterministic, fail-closed,
never cloud, raw-free. Reuses the existing router, eval harness, and hash-only receipt table.

## What was NOT implemented

- No change to the router decision logic, profiles, or routing config (reused as-is).
- No new model route or cloud path; no schema change.
- No new eval module — the existing `run_model_eval` synthetic harness provides the eval summary.

## Files

`00-repo-truth-audit.md`, `01/02-routing-diagnostics-final-output.{json,md}`,
`03-eval-summary-final-output.json`, `04-model-unavailable-proof.md`, `05-schema-failure-proof.md`,
`06-no-cloud-fallback-proof.txt`, `07-no-raw-persistence-proof.txt`, `08-safety-scan-results.txt`,
`09-production-db-unchanged-proof.txt`, `validation-commands.txt`, `validation-results.md`,
`final-output-manifest.md`, `changed-files.txt`, `branch-state.txt`.

## Safety checks

No raw bodies/prompts/responses/URLs/tokens/secrets/email dumps (safety scan: 0 findings). No cloud
fallback (no_cloud across all probes + config guardrail). No raw persistence (receipts table has no
raw columns + 13 guard columns). Production DB unchanged.

## Merge readiness

Merge-ready by itself: additive read-only diagnostics module + CLI verb, fully tested (5 new tests;
87 targeted green), lint/type clean.
