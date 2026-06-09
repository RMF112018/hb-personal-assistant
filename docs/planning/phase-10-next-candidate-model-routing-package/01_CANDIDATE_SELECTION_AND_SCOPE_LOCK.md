# 01 — Candidate Selection and Scope Lock

## Objective

Lock the next candidate after the daily-run pilot: local model evaluation + routing for daily-brief intelligence quality. Produce a repo-truth implementation plan before code changes.

## Scope boundaries

- Planning and optional docs-only scope lock.
- No implementation until scope is locked.
- Do not alter scheduler/daily-run work except to identify integration points.

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


## Candidate decision

Exclude these from selection because they are in progress or already covered by Checkpoint 6:
- Production-like daily pipeline pilot and operator runbook.
- Polished browser presentation family.
- Obsidian vault output family.
- Scheduler / launchd automation family.
- Pipeline health / run-status family, except as integration consumers.

Select:
- Local model evaluation and routing family, with daily-brief intelligence quality as the first consumer.

## Required repo-truth audit

Identify likely files:
- CLI registration file(s) for `second-brain`.
- Local model readiness/status implementation.
- Structured-output client and local model client.
- Daily-brief synthesis/render/pipeline/daily-run modules.
- Existing test files for local model, action intelligence, daily brief, pipeline, daily-run.
- Config resources for agents/model profiles.
- Migration/store modules if persistence is justified.

Identify likely DB tables:
- `daily_brief_action_candidates`.
- Any existing local model status/receipt/config tables.
- Any existing agent registry/performance tables.
- Any candidate guard columns.

## Required plan

Produce a concise implementation plan covering:
- Whether the model eval results persist to DB or only emit local JSON/evidence.
- Fixture strategy: redacted fixtures, synthetic fixtures, DB-copy derived fixtures, and raw local-only operator samples.
- Router config format.
- CLI command names.
- Integration point for optional daily-brief enrichment.
- Tests required.
- Live proof plan.
- Evidence plan.
- Explicit non-goals.

## Validation required

Run read-only inspections and `--help` commands only. Do not run live model evaluation yet.

## Stop conditions

- No local model client exists and implementation would require credential/auth changes.
- Current daily-run pilot branch has uncommitted changes that cannot be isolated.
- Candidate scope requires raw prompt/response persistence.
- Candidate scope requires cloud LLM use.

## Commit behavior

Commit only if you create or update a docs-only scope file. Suggested message:

```bash
git commit -m "docs(local-ai): lock model routing candidate scope"
```

## Final response format

Return:
- Candidate selected.
- Why alternatives were rejected.
- Files/tables/CLI likely involved.
- Implementation plan.
- Validation completed.
