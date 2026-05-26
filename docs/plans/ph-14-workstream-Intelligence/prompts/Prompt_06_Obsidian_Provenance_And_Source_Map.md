# Prompt 06 — Obsidian Provenance and Source Map

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

Add source maps and written_to_note provenance for generated notes.

## Likely Files / Modules Touched

obsidian/writer.py, obsidian/brief.py, links/registry.py, tests

## Required Work

1. Add source map output to brief generation.
2. Add action identity comments or equivalent stable source identifiers to generated task lines.
3. Implement `written_to_note` source-link recording for apply mode, or document a repo-truth-compatible alternative if notes are not modeled as source records.
4. Dry-run must report would-write and would-link behavior without mutation.
5. Add tests proving marker preservation, frontmatter merge, task-state preservation, dry-run no mutation, and apply-mode provenance.

## Validation Commands

pytest obsidian tests; brief dry-run command/path; sensitive scan.

Use the relevant commands from the baseline as needed:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant run morning --dry-run --json
```

## Acceptance Criteria

Generated notes are source-traceable and user content outside markers is preserved.

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
feat(obsidian): record source links for generated notes
```
