# Scope Lock — Daily Brief Usefulness Repair

This package fixes the daily brief's usefulness substrate. It is not a new product surface and not a model-replacement project.

## In Scope

- Calendar project alias/category resolution for daily-brief meeting prep.
- Procore signal ranking, demotion, and aggregate suppression.
- Deterministic daily-brief candidate projection.
- Source-ref coverage gates for model-facing brief context.
- Usefulness gates for daily-run success/partial/degraded status.
- Tests, DB-copy proof, and safe evidence.

## Out of Scope

- Cloud LLMs.
- Graph/Procore/calendar/email writeback.
- Scheduler activation.
- Full email follow-up raw-enrichment expansion.
- New UI surfaces beyond existing browser/Obsidian/status.
- Broad refactors unrelated to daily brief usefulness.
- Production DB mutation for validation.

## Primary Diagnosis

The DB contains useful source data, but the daily brief lacks a useful model-facing projection:

- Calendar rows exist but project-like meetings are unresolved.
- Procore rows exist but the top selection is dominated by unranked aggregate backlog.
- Daily-brief candidates are absent for the audited target date.
- Candidate source refs are absent.
- Follow-up/email enrichment sources are empty.
- The daily run reports success despite projection contradictions.

The fix is deterministic read-model and gate repair before prompt/model work.
