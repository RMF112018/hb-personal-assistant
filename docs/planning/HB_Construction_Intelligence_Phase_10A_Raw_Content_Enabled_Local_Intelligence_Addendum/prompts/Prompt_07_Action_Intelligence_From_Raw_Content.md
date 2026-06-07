# Prompt 07 — Action Intelligence From Raw Content

## Objective

Use local models to extract candidates from raw content.

## Tasks

1. Use strict schema.
2. Add business-contract validation.
3. Reject generic data-cleaning/data-analysis hallucinations.
4. Add retry/repair.
5. Persist candidates with raw source excerpts.

## Acceptance

- Model produces useful task/commitment/follow-up candidates from fixture raw email.
- Bad/generic candidates are rejected.
