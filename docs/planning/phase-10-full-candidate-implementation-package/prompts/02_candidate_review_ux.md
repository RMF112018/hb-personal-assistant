# Prompt 02 — Candidate Review UX

## Objective

Implement or materially improve the Candidate Review UX for Phase 10 local-agent outputs.

The UX may be CLI-first if that matches repo truth. It must allow Bobby/operator to inspect, filter, preview, accept/reject, and apply bounded review-safe local candidates without needing to inspect raw DB rows.

This candidate must produce final operator-facing review outputs and end-to-end evidence.

## Required repo-truth audit before implementation

Inspect current code paths for:

- action/task/commitment candidates
- daily brief action candidates
- follow-up watch candidates
- relationship candidates
- pending V45 email follow-up enrichments
- existing candidate review CLI or similar review surfaces
- apply/persist safety gates
- candidate source references and statuses

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/02-candidate-review-ux/00-repo-truth-audit.md
```

## Implementation requirements

1. Provide a coherent review command surface.

   Prefer extending an existing Typer command group if one exists. Do not invent a second parallel CLI if repo truth already has one.

   The UX should support, as applicable:

   - list pending candidates
   - filter by candidate type/source/project/status/confidence
   - show candidate detail
   - preview apply effects
   - accept/reject candidate
   - apply accepted candidates under bounded caps
   - export review-safe JSON/Markdown

2. All review operations must be dry-run by default.

   Apply must require explicit `--apply` and a cap, unless the existing repo policy provides an equivalent guard.

3. Make final output legible.

   Add a final operator-facing Markdown or terminal-style report that shows:

   - what is pending
   - what is accepted/rejected
   - what would be persisted
   - what was persisted
   - what requires Bobby's review
   - source references
   - confidence/safety reasons

4. Preserve safety.

   The review UX must not expose raw email/document bodies, raw prompts/responses, secrets, signed URLs, join links, or email-address dumps.

5. Keep old command paths working unless repo truth proves they are dead and tests/docs are updated.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/02-candidate-review-ux/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `01-review-list-final-output.md`
- `02-review-detail-final-output.md`
- `03-review-export-final-output.json`
- `04-preview-apply-output.md`
- `05-apply-cap-proof.json`
- `06-reject-accept-proof.json`
- `07-safety-scan-results.txt`
- `08-production-db-unchanged-proof.txt`
- `validation-commands.txt`
- `validation-results.md`
- `final-output-manifest.md`
- `changed-files.txt`
- `branch-state.txt`

Use synthetic or copied temp DB data if necessary to prove both empty and populated paths.

## Validation

Run targeted tests for candidate review CLI and persistence paths.

At minimum:

```bash
python -m compileall src tests
pytest -q tests -k "candidate or review or apply or daily_brief_action or followup"
```

Run lint/type checks on changed files.

## Commit

Suggested commit:

```text
feat(second-brain): add phase 10 candidate review ux
```

After committing, wait exactly 10 minutes before Prompt 03:

```bash
sleep 600
```
