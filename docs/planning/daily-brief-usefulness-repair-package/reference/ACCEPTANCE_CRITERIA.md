# Acceptance Criteria

The package is complete only when all criteria pass.

## Functional

- Near-term project-like calendar meetings are no longer all `__unassigned__`.
- Calendar internals/PTO/training are categorized separately from project meetings.
- Procore executive rows are not dominated by stale aggregate backlog.
- `daily_brief_action_candidates` or the repo's canonical daily-brief candidate read model is populated for target date on a DB copy.
- Daily-brief deterministic sections reflect source availability.
- Candidate/source-ref coverage is computed and enforced.
- Model synthesis consumes only gated source-linked deterministic rows.
- Usefulness gate prevents false `success`.

## Status / Output

- Status JSON includes usefulness gate metrics and verdict.
- Browser/Obsidian brief labels degraded/partial states clearly.
- Last successful brief is preserved on failure/degraded attempts.
- No browser auto-open is introduced.

## Safety

- No production DB mutation.
- No external writeback.
- No cloud model route.
- No raw bodies/prompts/responses/URLs/tokens in evidence/status/logs.
- Guard/writeback columns remain zero.
- Forbidden-string scan passes.

## Validation

- Unit tests for each priority pass.
- DB-copy live apply proof passes.
- Compileall passes.
- Changed-file lint/type checks pass or pre-existing failures are documented.
- Final handoff is complete.
