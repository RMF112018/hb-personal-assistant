# Prompt 05 — Promotion to Accepted Actions

## Objective

Make promotion from candidate to accepted item complete, idempotent, source-linked, and lifecycle-aware.

## Audit first

Verify current behavior for:

- task candidate -> `accepted_tasks`
- commitment candidate -> `accepted_commitments`
- daily-brief candidate -> domain candidate or lifecycle overlay
- follow-up watch item -> accepted task/commitment or managed watch state

## Required behavior

- Promotion is explicit; do not auto-promote new candidates.
- Promotion preserves deterministic IDs.
- Promotion preserves source refs directly or via a documented candidate-id link.
- Promotion preserves project key or `project_review_required`.
- Promotion does not duplicate accepted items.
- Promotion records acceptance timestamp and acceptance source.
- Promotion stores only redacted/bounded text.
- Promotion never copies raw bodies, HTML, recipient arrays, URLs, tokens, or model prompts/responses.

## Implementation guidance

- If accepted tables already reference the candidate ID and source refs are reliable through that candidate ID, document indirect source-ref propagation and add tests.
- If direct accepted-item source refs are needed for clean read-model behavior, prefer read-model joins over schema first.
- Add schema only if accepted items cannot be source-linked without ambiguity.

## Tests

Extend or add tests for:

- task accepted once
- commitment accepted once
- accepted source refs visible in lifecycle read model
- source-ref-missing accept fails/degrades
- daily-brief-only candidates either resolve to a domain candidate or are accepted as lifecycle-only with `promotion_skipped_unmapped`
- guard columns zero

