# Prompt 03 — Daily-Brief Candidate Projection

## Objective

Populate deterministic daily-brief sections from source rows before model synthesis.

## Problem

The audit found `daily_brief_action_candidates = 0` and empty deterministic sections despite calendar and Procore source rows.

## Required Implementation

1. Identify canonical projection tables/read models:
   - `daily_brief_action_candidates`
   - `daily_brief_source_refs`
   - `daily_brief_handoff_lines`
   - or repo-truth equivalent.
2. Implement/repair projection from calendar, ranked Procore rows, follow-up/watch/enrichment rows when available, and data gaps.
3. Candidate fields must include candidate id/stable key, brief date, section, title/redacted title, project/internal category, rank, urgency, reason/why today, next action, confidence/quality, source refs, and flags.
4. Projection must be idempotent on a copied DB.
5. Deterministic section counts must feed final status and model synthesis.
6. Do not use model output to create source facts.

## Tests

Synthetic projection from calendar, Procore, internal event, needs-review data gap, empty source graceful degradation, idempotency, caps, no raw persistence, no duplicates.

## Evidence

Create `docs/evidence/daily-brief-usefulness-repair/03-candidate-projection/`.

## Suggested Commit

`fix(second-brain): project source-linked daily brief candidates`
