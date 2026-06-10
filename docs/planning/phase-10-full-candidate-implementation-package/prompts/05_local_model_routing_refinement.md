# Prompt 05 — Local Model Routing Refinement

## Objective

Refine Phase 10 local model routing so each local-agent task uses an explicit, testable, fail-closed model profile with operator-visible diagnostics.

The implementation must improve routing reliability without introducing cloud fallback or raw prompt/response persistence.

## Required repo-truth audit before implementation

Inspect:

- model router
- model profile config
- evaluation harness
- structured output client
- provider availability probes
- existing task families
- daily-brief intelligence adapter
- email follow-up raw enrichment route
- tests and evidence for local model routing

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/05-local-model-routing-refinement/00-repo-truth-audit.md
```

## Implementation requirements

1. Define or confirm task profiles for all implemented Phase 10 candidates.

   At minimum, profile or explicit deterministic route coverage should exist for:

   - daily brief synthesis
   - email follow-up raw enrichment
   - candidate review summaries if model-assisted
   - relationship/entity normalization if model-assisted
   - document/file parsing classification if model-assisted
   - calendar/procore advisory summaries if model-assisted

2. Add routing diagnostics.

   The operator should be able to see:

   - profile selected
   - candidate model chain
   - availability/probe status
   - fallback reason
   - fail-closed reason
   - safety category
   - no raw prompts/responses

3. Add or improve local evaluation tasks.

   Include synthetic fixtures proving:

   - supported model available
   - model unavailable
   - malformed JSON/schema failure
   - low confidence output
   - no cloud fallback
   - no raw persistence

4. Preserve deterministic fallback.

   Operator-facing workflows must still provide deterministic output where possible when model routes fail.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/05-local-model-routing-refinement/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `01-routing-diagnostics-final-output.json`
- `02-routing-diagnostics-final-output.md`
- `03-eval-summary-final-output.json`
- `04-model-unavailable-proof.md`
- `05-schema-failure-proof.md`
- `06-no-cloud-fallback-proof.txt`
- `07-no-raw-persistence-proof.txt`
- `08-safety-scan-results.txt`
- `09-production-db-unchanged-proof.txt`
- `validation-commands.txt`
- `validation-results.md`
- `final-output-manifest.md`
- `changed-files.txt`
- `branch-state.txt`

## Validation

At minimum:

```bash
python -m compileall src tests
pytest -q tests -k "model_router or model_eval or structured_output or local_model or daily_brief_intelligence"
```

Run lint/type checks on changed files.

## Commit

Suggested commit:

```text
feat(second-brain): refine phase 10 local model routing
```

After committing, wait exactly 10 minutes before Prompt 06:

```bash
sleep 600
```
