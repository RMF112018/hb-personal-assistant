# Prompt 05 — MVP-Critical Validation Scope Reduction

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Reduce overly broad Ruff/mypy exclusions for MVP-critical modules without attempting a full-codebase cleanup.

## Target Strict Scope

Attempt to bring these under Ruff/mypy where practical:

```text
src/hb_assistant/actions
src/hb_assistant/automation
src/hb_assistant/obsidian
src/hb_assistant/retrieval/context.py
src/hb_assistant/cli/actions.py
src/hb_assistant/cli/run.py
tests/test_actions*.py
tests/test_automation*.py
tests/test_obsidian*.py
```

## Rules

- Do not broad-refactor unrelated legacy modules.
- Do not weaken tests just to pass.
- If a module remains excluded, document why and propose the next shrink step.
- Preserve behavior.

## Required Validation

```bash
.venv/bin/ruff check .
mypy src
.venv/bin/python -m pytest
```

## Evidence

Create:

```text
docs/evidence/mvp-local-runtime/05-validation-scope-hardening.md
docs/evidence/mvp-local-runtime/outputs/ruff.txt
docs/evidence/mvp-local-runtime/outputs/mypy.txt
docs/evidence/mvp-local-runtime/outputs/pytest.txt
```

## Commit Message

```text
chore(validation): tighten MVP runtime lint and type scope
```
