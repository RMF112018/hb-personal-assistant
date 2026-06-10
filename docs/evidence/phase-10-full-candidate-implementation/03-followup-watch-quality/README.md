# Evidence — 03 Follow-up Watch Quality

Candidate: `followup-watch-quality` · Prompt: `prompts/03_followup_watch_quality.md`
Branch: `experiment/phase-10-full-candidate-implementation` · Baseline: `0c75f4a7…`

## Scope

Improved follow-up watch operator usefulness: a deterministic, review-safe report that groups accepted
tasks/commitments by **operator action** (needs Bobby action / waiting on others / stale / monitor /
closed / needs-review), with deterministic quality gates that route no-source-ref (insufficient
evidence) and contradictory-signal items to a needs-review bucket and mark them non-actionable. New
`second-brain follow-up-watch report` verb (JSON/Markdown). No model, no writeback, no schema change.

## What was NOT implemented

- No change to the existing deterministic classifier or scan/persist path (reused as-is).
- No new daily-brief section (avoids duplicating the Prompt 01 V45 pending section).
- No model-assisted classification (kept fully deterministic).

## Files

`00-repo-truth-audit.md`, `01/02-followup-watch-final-output.{md,json}` (operator report),
`03-stale-followup-proof.json`, `04-closed-loop-proof.json`, `05-waiting-state-proof.json`,
`06-model-unavailable-proof.md`, `07-daily-brief-consumption-proof.md`,
`08-safety-scan-results.txt`, `09-guard-column-proof.json`, `10-production-db-unchanged-proof.txt`,
`validation-commands.txt`, `validation-results.md`, `final-output-manifest.md`, `changed-files.txt`,
`branch-state.txt`.

## Safety checks

No raw bodies/prompts/responses/URLs/join-links/tokens/secrets/email dumps (safety scan: 0 findings).
No external writeback. No cloud LLM (deterministic, no model). Guard columns zero on
`follow_up_watch_items` + `follow_up_status_events`. Production DB unchanged.

## Merge readiness

Merge-ready by itself: additive read-only command + deterministic helpers, fully tested (3 new tests;
165 targeted green), lint/type clean.
