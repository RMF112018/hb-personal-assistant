# 09 — Final Audit and Handoff

## Objective

Conduct a final repo-truth audit of the completed local model evaluation + routing family and produce a concise implementation handoff.

## Scope boundaries

- Audit/fix only.
- Do not start another candidate.
- Do not modify main.
- Do not merge.

Hard constraints:
- Do not modify `main`. Work only on the approved experiment branch for this package.
- Do not merge, rebase main, or imply a merge.
- No cloud LLM submission unless Bobby separately approves it.
- No automatic email send.
- No calendar mutation.
- No Procore writeback.
- No Graph writeback.
- No external writeback.
- No MCP raw exposure.
- No production DB mutation unless explicitly approved.
- No destructive migration unless explicitly approved.
- No credential/auth changes unless explicitly approved.
- No raw email/calendar/Procore/document body content committed to repo.
- No raw prompts, raw model responses, signed URLs, download URLs, join URLs, access tokens, refresh tokens, secrets, credential material, or unsafe HTML committed to repo, evidence, docs, tests, or logs.
- Raw local content may be used only for local operator consumption where explicitly allowed and must never be persisted to guarded candidate/evidence tables.
- Default persisted rows and repo evidence must remain redacted/guarded.
- Any apply/persist behavior must be capped, bounded, idempotent, source-linked, and review-safe.


## Required final audit

Re-run branch guard:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
```

Audit:
- Commit chain.
- Files changed.
- Schema changes and migration status.
- Config resources.
- CLI surfaces.
- Tests.
- Live workflow proof.
- Evidence redaction.
- No raw prompt/response.
- No cloud route.
- No writeback.
- Daily-run baseline not regressed.
- Deterministic fallback behavior.

## Required final validation

Run a final narrowed validation suite:
```bash
.venv/bin/python -m pytest <all-new-and-affected-tests>
.venv/bin/ruff check <changed-files-and-tests>
.venv/bin/ruff format --check <changed-files-and-tests>
.venv/bin/mypy <changed-src-files-or-package-scope>
```

Run final CLI smoke:
```bash
.venv/bin/hb-assistant second-brain local-model profiles --json
.venv/bin/hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json
.venv/bin/hb-assistant second-brain local-model eval --suite daily-brief --models auto --json
.venv/bin/hb-assistant second-brain daily-run run --dry-run --with-intelligence --json
```

## Acceptance criteria check

Complete the checklist in `ACCEPTANCE_CRITERIA.md`.

## Stop conditions

- Dirty tree at final handoff.
- Tests failing due this package.
- Any raw egress discovered.
- Any cloud route discovered.
- Any external writeback discovered.
- Daily-run deterministic fallback broken.

## Commit behavior

No commit unless final audit requires fixes. If fixes are needed, commit with a specific message.

## Final response format

Return:

```markdown
## Final Handoff

Branch:
HEAD:
Main HEAD:
Dirty tree:

## Commits

- ...

## Objective Completed

...

## Files Changed

...

## Schema / DB

...

## CLI Surfaces

...

## Tests and Validation

...

## Live Workflow Proof

...

## Guardrails

...

## Caveats / Pre-existing Failures

...

## Rollback

...

## Recommended Next Candidate

...
```
