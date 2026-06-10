# Evidence — 07 Relationship / Entity Normalization

Candidate: `relationship-entity-normalization` · Prompt: `prompts/07_relationship_entity_normalization.md`
Branch: `experiment/phase-10-full-candidate-implementation` · Baseline: `0c75f4a7…`

## Scope

Added a consolidated, read-only **relationship/entity review report** (`relationship-candidates
report`) that groups the unified V25 cross-source candidates by operator category (alias/project,
relationships, likely-duplicate entities, low-confidence needs-review, rejected/not-actionable) using
deterministic stable enums. Read-only — persists nothing, promotes nothing; a promotion-safety check
proves unreviewed/model-proposed inferences are never in an accepted state.

## What was NOT implemented

- No change to the substrate, scan, or entity tables (reused as-is).
- No model-based grouping (deterministic enums only).
- No new promotion/apply path — the bounded apply remains `relationship-candidates scan --apply`.
- No schema change.

## Files

`00-repo-truth-audit.md`, `01/02-relationship-candidates-final-output.{md,json}`,
`03-dedupe-proof.json`, `04-alias-match-proof.json`, `05-low-confidence-proof.md`,
`06-daily-brief-context-proof.json`, `07-apply-cap-or-dry-run-proof.json`,
`08-safety-scan-results.txt`, `09-guard-column-proof.json`, `10-production-db-unchanged-proof.txt`,
`validation-commands.txt`, `validation-results.md`, `final-output-manifest.md`, `changed-files.txt`,
`branch-state.txt`.

## Safety checks

No raw bodies/prompts/responses/URLs/tokens/secrets/email dumps (safety scan: 0 findings). No
writeback, no promotion. Guard columns zero on `cross_source_relationship_candidates`. Production DB
unchanged.

## Merge readiness

Merge-ready by itself: additive read-only report module + CLI verb, fully tested (4 new tests; 287
targeted green), lint/type clean.
