# Addendum Prompt 05: Implement Bounded Body Mention Detection Beyond Preview

## Objective

Close the functional MVP gap requiring detection of Bobby mentions in the email body even when not visible in `bodyPreview`.

## Starting Checks

Run and capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
source .venv/bin/activate
python --version
hb-assistant --version
```

## Operating Rules

- Do not re-run broad feature work from the prior remediation package.
- Keep the patch scoped to this addendum prompt.
- Do not enable Microsoft 365 writeback.
- Do not persist full email bodies.
- Do not commit tokens, PEM contents, SQLite DB files, token caches, or private `.env` files.
- Evidence must be truthful. If a command fails, record it as failed.
- Do not claim final acceptance until Addendum Prompt 06 is green.

## Problem Context

Current classification still operates on `body_preview_redacted`. That does not satisfy the original body-mention requirement.

## Tasks

### 1. Add a bounded body inspector

Create a service such as:

```text
src/hb_assistant/classification/body_inspector.py
```

Responsibilities:

- accept bounded body text in memory;
- strip/simplify HTML safely;
- detect Bobby aliases;
- return:
  - `body_mention_detected`;
  - `detection_method`;
  - `confidence`;
  - optional redacted match window;
  - no raw body.

### 2. Update MailClient

Add a method that retrieves bounded body content without persisting it:

```python
get_message_body_for_inspection(message_id: str, max_chars: int) -> BodyInspectionCandidate
```

Rules:

- select only needed fields;
- body content processed in memory only;
- truncate to config cap;
- never write raw body to DB/log/evidence.

### 3. Update classifier

Classifier should support:

- preview-only detection;
- bounded-body fallback when preview does not mention Bobby;
- detection method stored or returned.

### 4. Update store minimally

If schema changes are needed, add additive columns only, for example:

- `body_detection_method`
- `body_match_excerpt_redacted`

If avoiding schema change, include detection method in classification output and source link metadata if already supported.

### 5. Tests

Add tests proving:

- Bobby appears only outside preview and is detected;
- HTML body mention is detected;
- raw body is not persisted;
- output contains no full body;
- no To/Cc is required for body detection to include the email.

## Required Validation

```bash
python -m pytest tests/test_classification.py tests/test_body_mentions.py tests/test_graph_clients.py
hb-assistant diagnostics classify --json
hb-assistant diagnostics scan-sensitive --repo . --json
```

## Expected Result

Original MVP body-mention requirement is satisfied.

## Evidence Required

Create/update:

```text
docs/evidence/remediation-addendum/prompt-05/
```

Include:

- `commands.md`
- command output files
- `summary.md`
- `known-issues.md`

## Required Commit

```text
feat(mail): add bounded body mention detection beyond preview
```
