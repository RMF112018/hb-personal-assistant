# Prompt 05 — Workstream Context Builder Upgrade

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

Build a source-linked workstream context that can feed brief generation and search.

## Likely Files / Modules Touched

retrieval/context, obsidian/brief.py, tests

## Required Work

1. Inspect current `WorkstreamContextBuilder` and extend it additively.
2. Include open actions, waiting-on items, upcoming calendar rows, file review queue, body mentions, and retrieval hits.
3. Ensure each context item includes source IDs/source links where available.
4. Update `DailyBriefGenerator` only as needed to consume richer context.
5. Add deterministic tests for seeded and empty stores.

## Validation Commands

pytest retrieval/context/brief tests; `hb-assistant search` smoke.

Use the relevant commands from the baseline as needed:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant run morning --dry-run --json
```

## Acceptance Criteria

Context builds without Graph consent and carries source traceability.

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
feat(context): build source-linked workstream context
```
