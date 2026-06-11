# Source Ref Propagation Contract

## Rules

- Every surfaced actionable row must have at least one source ref or be withheld/degraded.
- Accepted items must be traceable to source refs through:
  1. direct accepted-item source refs, or
  2. accepted row `candidate_id` -> `candidate_source_refs`
- Merge must preserve source and target refs in the read model.
- Suppression must not delete refs.
- Feedback summaries may count source refs but must not emit raw source content.

## Coverage metrics

- `source_ref_count`
- `source_ref_coverage_status`
- `executive_source_ref_coverage`
- `accepted_source_ref_coverage`
- `merged_source_ref_preserved_count`

