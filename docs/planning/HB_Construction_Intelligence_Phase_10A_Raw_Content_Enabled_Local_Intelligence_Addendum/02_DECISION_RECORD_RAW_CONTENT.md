# 02 Decision Record — Raw Content Enabled

## Decision

Raw email and calendar content is allowed for local intelligence workflows.

## Reason

Metadata-only exports cannot reliably support:

- task extraction;
- commitment detection;
- due-date extraction;
- waiting-on-me/waiting-on-others classification;
- follow-up detection;
- meeting prep;
- project relationship inference;
- Daily Brief action intelligence.

## New principle

The system should distinguish between:

- local raw-content processing, which is allowed;
- external raw-content exposure, which remains a separate approval decision;
- source-system writeback, which remains out of scope.

## Product stance

Raw content is not a bug or policy violation in this phase. It is a required feature.

## Required implementation posture

- Config must explicitly state raw content is enabled.
- Diagnostics must show raw content mode.
- Evidence must show raw content counts.
- Model context should use bounded raw content.
- Review UI should surface raw content where useful.
