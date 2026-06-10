# Prompt 07 — Relationship / Entity Normalization

## Objective

Implement the next Phase 10 relationship/entity normalization candidate.

The goal is to improve entity aliasing, dedupe, project/source association, and relationship candidate quality in review-safe form, with no external writeback.

## Required repo-truth audit before implementation

Inspect:

- relationship candidate engine
- project aliasing
- entity/person/company/project tables
- email/calendar/source references
- daily-brief context packet relationship handling
- accepted candidate review/promotion paths
- existing tests/evidence for relationships/entity normalization

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/07-relationship-entity-normalization/00-repo-truth-audit.md
```

## Implementation requirements

1. Improve deterministic normalization first.

   Prefer explicit alias tables, stable keys, source references, and confidence reasons over model-only inference.

2. Provide review-safe relationship/entity candidate output.

   The final output should group candidates by:

   - likely duplicate entities
   - alias/project matches
   - person/company/project relationships
   - low-confidence needs-review records
   - rejected/not-actionable candidates

3. Preserve source traceability.

   Every candidate must cite safe source IDs. Do not expose raw message/document content.

4. Add safety and confidence gates.

   Low-confidence or conflicting candidates must remain advisory/review-required.

5. Integrate with daily brief context where appropriate.

   Relationship candidates may help daily brief grouping, but unreviewed relationship inferences must not become accepted facts.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/07-relationship-entity-normalization/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `01-relationship-candidates-final-output.md`
- `02-relationship-candidates-final-output.json`
- `03-dedupe-proof.json`
- `04-alias-match-proof.json`
- `05-low-confidence-proof.md`
- `06-daily-brief-context-proof.json`
- `07-apply-cap-or-dry-run-proof.json`
- `08-safety-scan-results.txt`
- `09-guard-column-proof.json`
- `10-production-db-unchanged-proof.txt`
- `validation-commands.txt`
- `validation-results.md`
- `final-output-manifest.md`
- `changed-files.txt`
- `branch-state.txt`

## Validation

At minimum:

```bash
python -m compileall src tests
pytest -q tests -k "relationship or entity or alias or dedupe or candidate"
```

Run lint/type checks on changed files.

## Commit

Suggested commit:

```text
feat(second-brain): improve phase 10 relationship entity normalization
```

After committing, wait exactly 10 minutes before Prompt 08:

```bash
sleep 600
```
