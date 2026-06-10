# Prompt 01 — Calendar Project Alias Resolution

## Objective

Fix project/category resolution for calendar rows before they enter meeting-prep and daily-brief projection.

## Problem

The audit found 8 near-term calendar events, all with subjects and attendees, but `calendar_project_resolution_rate = 0.0`.

## Required Implementation

1. Locate current calendar prep/read-model code, likely `src/hb_assistant/construction/second_brain/local_ai/calendar_prep.py`.
2. Implement deterministic alias/category resolution:
   - input: subject, organizer, location, attendees, existing project fields;
   - output: `project_key`, `category`, `confidence`, `matched_alias`, `needs_review`, `reason`.
3. Categories: `project`, `internal_company`, `internal_training`, `internal_time_off`, `needs_review`, `unknown`.
4. Resolve from repo/project truth, not guesses.
5. Wire resolver into calendar prep before candidate/projection output.
6. Ensure brief can show project meetings, internal events, and data gaps separately.

## Initial Alias Expectations

- `Wellington` may map to `the-wellington` only if repo truth supports it.
- `Hilltop` / `Alton Hilltop` may map to `hilltop` or `alton-hilltop-pbg` only if repo truth supports it.
- `TWN` requires verification; if ambiguous, route to `needs_review`.
- `PTO` and `Training` must not be project unknown.
- Financial Forecast should be internal/company or needs-review.

## Tests

Create/extend tests for exact alias, case-insensitive token, ambiguous token, internal/company, PTO, training, multiple signals, low-confidence review-safe, and no raw body requirements.

## DB-Copy Probe

Using a DB copy, prove that calendar projection no longer leaves all project-like meetings unresolved.

## Evidence

Create `docs/evidence/daily-brief-usefulness-repair/01-calendar-alias-resolution/`.

## Suggested Commit

`fix(second-brain): resolve calendar project aliases for brief candidates`
