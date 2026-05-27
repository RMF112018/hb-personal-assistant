# 02 — Repo-Truth Audit Requirements

## Starting Commands

Run and capture:

```bash
git remote -v
git branch --show-current
git rev-parse HEAD
git log --oneline -20
git status --short
```

Expected HEAD:

```text
baac7b5cf61d461d3b544262d02ad4c051aa9fa1
```

If HEAD differs, stop and document the actual state before modifying files.

## Required File/Code Inspection

Use targeted greps before opening files:

```bash
grep -R "extract_candidates" -n src/hb_assistant/automation src/hb_assistant/actions tests || true
grep -R "ActionService" -n src/hb_assistant/automation src/hb_assistant/actions tests || true
grep -R "written_to_note" -n src/hb_assistant tests docs/evidence || true
grep -R "record_link" -n src/hb_assistant/obsidian src/hb_assistant/automation tests || true
grep -R "mentions: list" -n src/hb_assistant/retrieval || true
grep -R "list_recent_body_mentions" -n src/hb_assistant tests || true
grep -R "ignore_errors = true\|extend-exclude\|follow_imports = \"skip\"" -n pyproject.toml || true
grep -R "app-only\|application permission\|Mail.Read" -n src/hb_assistant docs tests || true
```

## Truth Hierarchy

1. Actual code behavior.
2. Tests that execute behavior.
3. Captured command output.
4. Evidence JSON/markdown.
5. Architecture docs.
6. Commit messages.

Docs are not proof unless matched by code/tests/evidence.

## Key Questions

- Does `run morning` call the actual implemented action extraction method?
- Does dry-run mutate only what policy allows?
- Is `written_to_note` actually persisted on apply path?
- Are body mentions first-class in workstream context?
- Do seeded/fixture local signals produce nonzero actions?
- Are Graph consent blockers isolated as external and nonfatal?
- Are Ruff/mypy exclusions still too broad?
- Is there a single operator-readable MVP evidence bundle?
