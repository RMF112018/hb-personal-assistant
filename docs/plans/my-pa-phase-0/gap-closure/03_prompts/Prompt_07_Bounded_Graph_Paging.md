# Prompt 07: Bounded Graph Paging

## Objective

Implement bounded paging in Graph read clients so the assistant does not silently miss data beyond the first page.

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
- Create evidence under `docs/evidence/remediation/prompt-07-*/`.

## Tasks

1. Update `MailClient` so `list_inbound()` and `list_sent()` use `get_all_pages()` with max item/page caps.
2. Update `CalendarClient` so calendarView uses paging.
3. Update `DriveItemClient` so children and attachments use paging.
4. Add config caps:
   - max mail items per run;
   - max calendar items per run;
   - max drive items per run;
   - max Graph pages per call.
5. Ensure paging remains deterministic and bounded.
6. Add mocked `@odata.nextLink` tests.

## Validation

```bash
python -m pytest tests/test_graph*.py tests/test_mail*.py tests/test_calendar*.py
hb-assistant diagnostics graph --safe --json
```

## Required Commit

```text
feat(graph): add bounded paging to read clients
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
