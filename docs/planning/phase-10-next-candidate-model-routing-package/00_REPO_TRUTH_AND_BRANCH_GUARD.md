# 00 — Repo Truth and Branch Guard

## Objective

Verify live repository truth before any implementation. Confirm that the production-like daily pipeline pilot/operator runbook is not the selected candidate for this package because it is already in progress or present. Establish a safe experiment branch for local model evaluation + routing.

## Scope boundaries

- Read-only audit only.
- Do not modify files.
- Do not modify DBs.
- Do not install scheduler items.
- Do not run model prompts against raw private data in this step.

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


## Required commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
git log --oneline --decorate -n 20
```

If current branch is `main`, create/switch to:

```bash
git switch -c experiment/local-model-routing-daily-brief-intelligence
```

unless Bobby has provided a different branch name.

## Audit requirements

Verify:
- Current branch and HEAD.
- Dirty tree.
- Whether any daily-run pilot work is in progress.
- Whether Checkpoint 6 daily-run/scheduler/browser/status work exists in code, docs, or pending tree.
- Current schema version and latest migration.
- Current local model CLI surfaces.
- Current daily brief, pipeline, calendar-prep, procore-digest, follow-up-watch CLI surfaces.
- Existing tests and known pre-existing failures.
- Whether any uncommitted work belongs to another checkpoint.

## Commands to inspect CLI surfaces

```bash
.venv/bin/hb-assistant second-brain --help
.venv/bin/hb-assistant second-brain local-model --help
.venv/bin/hb-assistant second-brain daily-brief --help
.venv/bin/hb-assistant second-brain pipeline --help
.venv/bin/hb-assistant second-brain daily-run --help || true
.venv/bin/hb-assistant second-brain daily-run scheduler --help || true
```

## Stop conditions

- Active branch is `main` and branch switch is not authorized.
- Dirty tree contains unrelated daily-run pilot work.
- Local DB cannot be identified safely.
- Repo state contradicts this package enough that selected candidate is no longer appropriate.

## Commit behavior

No commit.

## Final response format

Return:
- Branch/HEAD/tree summary.
- Main HEAD.
- Daily-run pilot status: absent / in progress / implemented.
- Confirmed selected candidate: local model evaluation + routing.
- Proceed / stop recommendation.
