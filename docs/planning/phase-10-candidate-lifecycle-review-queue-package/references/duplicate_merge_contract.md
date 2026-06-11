# Duplicate and Merge Contract

## Duplicate group key

Use the first available deterministic basis:

1. `source_family + source_ref_hash`
2. `thread_ref` or `message_id_hash`
3. `stable_key`
4. `family + project_key + normalized_redacted_title_hash + due_bucket`
5. `subject_type + subject_id`

## Merge

- Source item state becomes `merged`.
- Target remains canonical.
- Source refs from source remain visible in canonical target's merged-source summary.
- Replaying same merge is a no-op.
- Merged source is hidden from normal daily brief/review but visible with explicit filters.

## Suppression

- Candidate-level suppression hides that subject.
- Group-level suppression hides future candidates with the same duplicate group key.
- Suppression is auditable and reversible through reopen/unsuppress if implemented.

