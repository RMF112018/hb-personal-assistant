# Prompt 07 — Morning Run Orchestration Upgrade

You are operating in the local `RMF112018/hb-personal-assistant` repository. Follow repo truth. Do not invent files or APIs.

## Global Operating Rules for the Local Agent

- Work from repo truth only. Do not invent files, APIs, commands, schemas, or behavior.
- Do not re-read files that are still within your current context or memory. Only re-open files when you need to verify changed content, inspect lines not previously loaded, or confirm post-patch behavior.
- Before editing, capture the current repo state:
  - `git remote -v`
  - `git branch --show-current`
  - `git rev-parse HEAD`
  - `git log --oneline -20`
  - `git status --short`
- Keep every change Bobby-only and local-first.
- Do not add Microsoft 365 writeback.
- Do not add multi-user scope.
- Do not persist full email bodies.
- Do not persist full file contents.
- Do not move runtime state into cloud services.
- Do not classify delegated proof as a code failure if the live evidence shows tenant/admin consent is pending.
- Do not classify DNS as the active blocker unless current command evidence proves a live DNS failure.
- Prefer deterministic local fixtures and dry-runs while delegated Graph consent is pending.
- Preserve all existing user work. Do not delete unrelated untracked files or local artifacts.
- Commit after each prompt with the exact expected commit message unless repo truth requires a narrowly adjusted message.

## Objective

Upgrade run morning to execute full local stages while classifying Graph consent blockers.

## Likely Files / Modules Touched

automation/orchestrator.py, cli/run.py, tests

## Required Work

1. Upgrade `MorningRunOrchestrator` to use the stage model in `05_Local_Runtime_Orchestration_Specification.md`.
2. Classify Graph stages as skipped when no token/admin consent is pending, but continue local stages.
3. Integrate action extraction, context building, brief generation, Obsidian dry-run/write, ledger, and evidence.
4. Keep failure isolation for non-foundational stages.
5. Add tests for no-token, consent-blocked, DB blocked, dry-run, and isolated failure paths.

## Validation Commands

pytest automation/run tests; `hb-assistant run morning --dry-run --json`; sensitive scan.

Use the relevant commands from the baseline as needed:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant run morning --dry-run --json
```

## Acceptance Criteria

Morning dry-run succeeds locally while Graph consent is pending and reports structured stage statuses.

## Evidence Requirements

Create or update a prompt-specific evidence folder under:

```text
docs/evidence/phase-14-local-runtime-workstream-intelligence/
```

Include:

- `summary.md`
- relevant command outputs or summarized exit codes;
- validation notes;
- blocker classification if applicable;
- final commit SHA.

## Expected Commit Message

```text
feat(run): orchestrate full local morning workflow
```
