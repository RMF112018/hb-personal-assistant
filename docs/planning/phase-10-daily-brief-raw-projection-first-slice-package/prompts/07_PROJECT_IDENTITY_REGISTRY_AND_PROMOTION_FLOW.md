# 07 — Project Identity Registry / Review-Safe Promotion Flow

## Objective

Improve project-key resolution using existing project identity tables and deterministic alias/project source truth without unsafe auto-invention.

## Required behavior

1. Inventory existing tables/APIs:
   - `construction_project_identity`
   - `construction_project_keyword_registry`
   - `construction_project_source_matches`
   - `construction_source_locations`
   - relationship candidate tables
   - project alias config/read models

2. Implement or harden a read model that returns:
   - active project identities
   - aliases/keywords
   - source locations
   - candidate matches needing review
   - promoted matches

3. Add a deterministic promotion helper only if repo lacks one:
   - Promotes exact/high-confidence deterministic aliases.
   - Marks ambiguous/low-confidence mappings as review-required.
   - Never promotes a mapping from raw content without deterministic support.

4. Integrate project identity into calendar and candidate projection:
   - Project-key when confidently resolved.
   - `Needs Project Review`/sentinel when unresolved.
   - reason codes and confidence bands in receipts.

## Avoid overreach

Do not create a model-assisted autonomous promotion loop in this slice. The goal is deterministic improvement and review queue readiness.

## Evidence

Create `13-project-identity-resolution-proof.json` with counts only:

- identities count
- aliases/keywords count
- source locations count
- candidates promoted count
- needs-review count
- unresolved count
- project-key coverage before/after on copy

## Tests

- exact alias resolves
- ambiguous alias routes to review
- unknown project-like token routes to review
- no raw subject/title values in evidence/status

## Acceptance

- Project mapping is improved where deterministic truth exists.
- Unknowns are made visible rather than silently unassigned.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
