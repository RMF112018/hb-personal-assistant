# Prompt 06 — Procore Expansion

## Objective

Implement the next repo-truth-safe Procore expansion candidate.

The expansion should improve Procore monitoring/read-model usefulness for daily brief and operator review without adding unsafe Procore writeback.

Candidate scope should be determined by repo truth, but likely areas include:

- endpoint contract completion
- source refresh status clarity
- sync persistence path reconciliation
- Procore digest/read model output
- daily-brief Procore signal consumption
- project/source mapping improvements

## Required repo-truth audit before implementation

Inspect:

- Procore endpoint workflows
- Procore live source refresh
- scheduler/source-refresh execution
- Procore sync persistence
- Procore monitoring/read models
- downstream Procore digest/daily-brief consumers
- recent Procore evidence and architecture docs
- existing Procore tests

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/06-procore-expansion/00-repo-truth-audit.md
```

## Implementation requirements

1. Select the highest-ROI Procore implementation slice supported by repo truth.

   Do not implement broad speculative features. Prefer closing the next concrete gap that blocks reliable daily-brief Procore intelligence.

2. Keep Procore read-only.

   No creates, updates, deletes, or external mutations.

3. Improve final operator output.

   The Procore final output should show safe project-level signals such as:

   - source-refresh health
   - endpoint contract status
   - last sync status
   - degraded/missing endpoint reasons
   - project/source mapping status
   - safe digest items
   - source references

4. Preserve degraded honesty.

   If an endpoint is not implemented, not authorized, or degraded, output must say so clearly.

5. Add proof on temp/sanitized data.

   Do not require live Procore mutation or raw external payload persistence.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/06-procore-expansion/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `01-procore-digest-final-output.md`
- `02-procore-digest-final-output.json`
- `03-source-refresh-status-proof.json`
- `04-endpoint-contract-proof.md`
- `05-sync-persistence-proof.json`
- `06-daily-brief-consumption-proof.md`
- `07-degraded-endpoint-proof.md`
- `08-no-writeback-proof.txt`
- `09-safety-scan-results.txt`
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
pytest -q tests -k "procore or source_refresh or procore_digest or endpoint"
```

Run lint/type checks on changed files.

## Commit

Suggested commit:

```text
feat(second-brain): expand phase 10 procore read models
```

After committing, wait exactly 10 minutes before Prompt 07:

```bash
sleep 600
```
