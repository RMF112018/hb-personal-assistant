# 08 — Final Audit and Handoff

## Objective

Conduct a final repo-truth audit of the completed relationship candidate engine and produce a complete implementation handoff.

## Scope

Audit/handoff. Do not modify code unless a critical issue is found; if found, fix, test, and document.


## Non-Negotiable Constraints

- Target branch: `experiment/local-agent-family-proof` unless Bobby explicitly directs otherwise.
- Do not modify `main`; do not merge; do not retarget PRs.
- Treat live repo truth and DB truth as authoritative over this package.
- This package assumes the production-like daily pipeline pilot is already in progress or complete; do **not** re-implement scheduler, polished brief delivery, Obsidian delivery, or daily pipeline automation except for minimal integration hooks explicitly scoped here.
- No cloud LLM submission unless Bobby separately approves it.
- No automatic email send.
- No calendar mutation.
- No Procore writeback.
- No Graph writeback.
- No external writeback.
- No MCP raw exposure.
- No production DB mutation unless Bobby explicitly approves it.
- No destructive migration unless Bobby explicitly approves it.
- No credential/auth changes unless Bobby explicitly approves it.
- No raw email/calendar/Procore/document body content committed to repo, tests, evidence, docs, or logs.
- No raw prompts, raw model responses, signed URLs, download URLs, join URLs, access tokens, refresh tokens, secrets, credential material, or unsafe HTML committed to repo, evidence, docs, tests, or logs.
- Default persisted rows and repo evidence must remain redacted/guarded.
- Any apply/persist behavior must be capped, bounded, idempotent, source-linked, review-safe, and disabled by default.
- Raw local content may appear only in explicitly approved local operator-consumption surfaces and never in committed evidence.


## Final Audit Checklist

1. Branch/HEAD/tree/main proof.
2. Commit chain summary.
3. Changed file inventory.
4. Schema/migration status.
5. CLI surface proof.
6. Store/persistence proof.
7. Daily brief integration proof.
8. Pipeline regression proof.
9. Guardrail proof.
10. Tests/ruff/format/mypy proof.
11. Live DB-copy workflow proof.
12. Evidence redaction proof.
13. Stop conditions encountered or avoided.
14. Rollback instructions.
15. Next recommended candidate after this one.

## Required Commands

Run repo-truth equivalents of:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
git log --oneline --decorate -n 20
```

Run the full validation command set from `VALIDATION_COMMANDS.md`.

## Final Handoff Format

Use this structure:

```markdown
# Final Handoff — Phase 10 Relationship Candidate Engine

## Branch / Git State

## Objective Completed

## Commits Made

## Files Changed

## CLI Surfaces

## Tables / Schema

## Behavior Implemented

## Guardrails

## Validation Results

## Live Workflow Proof

## Daily Pipeline Regression Proof

## Evidence / Docs Updated

## Known Caveats / Pre-existing Failures

## Rollback

## Recommended Next Step
```

## Stop Conditions

- Dirty tree contains unexplained changes.
- Validation failed due to introduced issue.
- Evidence contains raw private data.
- `main` was modified without explicit authorization.

## Commit Behavior

Commit expected: no unless final audit discovers and fixes a blocking issue.

