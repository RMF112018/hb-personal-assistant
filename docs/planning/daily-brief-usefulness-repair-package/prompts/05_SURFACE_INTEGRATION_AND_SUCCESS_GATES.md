# Prompt 05 — Surface Integration and Success Gates

## Objective

Make daily-run status, browser output, and Obsidian output honest about usefulness.

## Required Implementation

1. Implement a usefulness gate after deterministic projection and before final success.
2. Gate metrics include calendar project resolution, unresolved project-like events, Procore aggregate sludge selected, Procore due/recent selected, candidate counts, source-ref coverage, project-key coverage, deterministic section count, supported/dropped synthesis bullets, contradiction flags, and final verdict.
3. Success requires at least one useful deterministic section, no source/deterministic contradiction, source-supported model bullets, 100% executive row source refs, project-like calendar not all unresolved, Procore top rows not aggregate sludge, and clean egress scan.
4. If gate fails, return `partial` or `degraded`, preserve last successful browser path, write attempted/degraded brief only if safe, and explain `usefulness_gate_failed`.

## Tests

Success, degraded empty sections, degraded zero source-ref coverage, degraded all calendar unresolved, aggregate Procore suppression, deterministic/synthesis mismatch, last-successful preservation, latest-successful not overwritten, status JSON shape.

## Evidence

Create `docs/evidence/daily-brief-usefulness-repair/05-usefulness-gates/`.

## Suggested Commit

`fix(second-brain): enforce daily-run usefulness status gates`
