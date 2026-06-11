# 05 — Calendar Candidate Projection and Project-Resolution First Pass

## Objective

Make calendar prep produce persisted, source-linked daily-brief candidates when useful in-window events exist, while improving deterministic project assignment and review-safe unresolved states.

## Required behavior

- Reuse `build_calendar_prep_candidates` and `persist_candidate_with_refs` where possible.
- Ensure apply mode persists candidates into `daily_brief_action_candidates` with `section = 'calendar'`.
- Ensure every persisted calendar candidate has at least one `candidate_source_refs` row.
- Keep source refs review-safe/hash-based.
- Use structured calendar rows when available; raw landing fallback is allowed only through existing safe read models and must not emit raw values into evidence/status.
- Classify meetings into useful/actionable, FYI, internal/company/training/PTO/non-project, needs-review, unknown.
- Persist/report project assignment confidence and needs-review reason codes where schema allows.

## Project resolution

Use deterministic sources only:

- Existing project alias/config registry.
- Existing source location/project source mappings.
- Exact/known project tokens.
- Existing `project_aliases.resolve_project` / `calendar_category.resolve_calendar_category`.

Do not invent project mappings. Ambiguous mappings should become `Needs Project Review` / `__needs_review__`.

## Candidate caps

- Apply mode must require a cap such as `max_persist`.
- Existing rows must be idempotently skipped, not duplicated.

## Status/receipt fields

- events in window
- events considered
- calendar candidates would persist / persisted / skipped existing
- assigned project count
- unassigned/needs-review count
- category distribution
- source-ref coverage

## Tests

Add synthetic tests for:

- one project meeting persists one source-linked candidate
- internal/PTO/training meeting does not become executive project action
- ambiguous project-like meeting becomes needs-review
- candidate source-ref coverage is 100%
- no raw join URLs/full attendees/raw body in candidate/status/evidence

## Acceptance

- Calendar source rows can no longer exist silently while calendar candidates remain zero unless every row is deliberately excluded with reason codes.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
