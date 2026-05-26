# Prompt 06: Bounded Body Mention Detection

## Objective

Satisfy the original requirement that emails are included when Bobby is mentioned in the body even if he is not in To/Cc.

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
- Create evidence under `docs/evidence/remediation/prompt-06-*/`.

## Required Behavior

The system must detect Bobby mentions that occur outside Graph `bodyPreview`.

## Tasks

1. Add a `BodyContentInspector` or equivalent service.
2. Retrieval policy:
   - Fetch full body only for bounded candidate messages.
   - Process body in memory.
   - Do not persist raw body.
   - Strip HTML safely if needed.
   - Apply max character limit.
3. Store only body flags, confidence, detection method, and optional short redacted match excerpt if allowed.
4. Update classification pipeline:
   - preview-first fast path;
   - bounded body fallback when preview does not mention Bobby and message is otherwise relevant.
5. Add tests:
   - Bobby appears only after preview window;
   - HTML body mention;
   - no raw body stored;
   - no full body in evidence/logs;
   - To/Cc absence but body mention still included.

## Validation

```bash
python -m pytest tests/test_classification.py tests/test_body_mentions*.py
hb-assistant diagnostics classify --json
hb-assistant diagnostics scan-sensitive --repo . --json
```

## Required Commit

```text
feat(mail): add bounded in-memory body mention detection
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
