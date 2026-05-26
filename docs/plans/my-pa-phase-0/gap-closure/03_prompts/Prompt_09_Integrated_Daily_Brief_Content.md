# Prompt 09: Integrated Daily Brief Content

## Objective

Replace stale “later phase” placeholder Daily Brief sections with real data-backed sections using existing store/retrieval/context services.

## Required Starting Checks

Run and capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
python --version
```

Do not proceed if the working tree contains unrelated uncommitted changes unless you first document them and isolate your patch.

## Agent Rules

- Do not trust prior closeout claims.
- Do not re-read files already in current context unless changed or required by failing tests.
- Do not enable Microsoft 365 writeback.
- Do not log or commit tokens, private keys, PEM bodies, full email bodies, or full file contents.
- Keep the patch tightly scoped to this prompt.
- Create evidence under `docs/evidence/remediation/prompt-09-*/`.

## Tasks

1. Refactor `DailyBriefGenerator` to accept or build `WorkstreamContext`.
2. Populate sections from available data:
   - Priority Actions from `action_items`;
   - Waiting On from action classification/source links;
   - Meeting Prep from calendar events;
   - File Review Queue from eligible/approved/pending files;
   - Project / Workstream Signals from retrieval hits and body mentions;
   - Sources from source links.
3. Remove stale text such as “Populated in later runs,” “after Phase 9,” and “later phase.”
4. Use empty-state language instead:
   - “No current file review candidates found.”
   - “No meeting prep items found for the configured window.”
5. Preserve marker-bounded write behavior.
6. Add tests for seeded DB output, empty DB output, and marker preservation.

## Validation

```bash
python -m pytest tests/test_obsidian*.py tests/test_brief*.py tests/test_retrieval.py
hb-assistant diagnostics brief --json
hb-assistant run morning --dry-run --json
```

## Required Commit

```text
feat(brief): wire daily brief to current context sources
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
