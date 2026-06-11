# 08 — Source-Ref, Evidence, and Usefulness Contradiction Gates

## Objective

Harden gates so the daily brief cannot report clean success when the substrate is empty, unsupported, or contradictory.

## Required gates

### Source-ref gate

- Executive sections: `actions`, `procore`, `calendar`, `follow_up`, `waiting` require 100% candidate source-ref coverage for clean success.
- Candidates lacking source refs must be dropped from model context or force degraded status.
- Gate report must include total, linked, uncovered, coverage, executive coverage, and verdict.

### Usefulness gate

Compute a daily usefulness verdict using counts only:

- projection status
- daily candidate count
- calendar candidate count
- Procore candidate count
- candidate source-ref coverage
- project-key coverage / needs-review count
- data gaps
- suppressed backlog count

### Contradiction detector

Known-bad contradictions:

- Calendar source rows in window exist but calendar candidates are zero and not all events have explicit excluded reasons.
- Procore open/promotable source rows exist but Procore candidates are zero and not explicitly suppressed.
- Email raw/thread rows exist but follow-up/task layers are empty without data-gap status.
- Source-ref gate says no candidates/source links but model synthesis proceeds as success.

## Status behavior

- Clean success only when gates pass.
- Degraded when source data exists but downstream projection/candidate layers are missing.
- Failed/blocked when projection fails due to unmapped fields or unsafe conditions.

## Tests

Add known-bad tests that seed source rows with zero candidates and assert non-success/degraded status.

## Evidence

Create:

- `14-candidate-source-ref-coverage.json`
- `15-usefulness-gate-proof.json`
- `16-contradiction-known-bad-proof.json`

## Acceptance

- Misleading success is eliminated for the known bad cases.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
