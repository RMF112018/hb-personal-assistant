# 12 — Testing, Validation, and Evidence Plan

## Objective

Define the validation plan for Phase 14.

## Test Layers

### Unit Tests

- action phrase detection;
- waiting-on detection;
- stable key generation;
- confidence scoring;
- source-link helper behavior;
- Obsidian marker preservation;
- blocker taxonomy classification helpers.

### Store Tests

- action upsert idempotency;
- completed action preservation;
- source-link creation;
- migration idempotency;
- no duplicate action rows on repeated extraction.

### CLI Tests

- `actions extract --dry-run --json`;
- `actions list --json`;
- `run morning --dry-run --json`;
- JSON shape and exit codes;
- consent-blocked/no-token behavior.

### Orchestrator Tests

- no delegated token -> Graph stage skipped, local stages continue;
- admin consent blocker -> external-blocked classification, local stages continue;
- DB unavailable -> foundational blocked status;
- isolated parser/action failure -> stage error, run continues;
- dry-run -> no Obsidian write, no action mutation unless command explicitly applies.

### Security Tests

- no full body persistence;
- no full file content persistence;
- no token/secret/PEM leakage;
- sensitive scan remains clean.

## Evidence Directories

Recommended new evidence path:

```text
docs/evidence/phase-14-local-runtime-workstream-intelligence/
```

Suggested subdirectories:

```text
prompt-00-repo-truth/
prompt-01-blocker-taxonomy/
prompt-02-actions-module/
prompt-03-action-persistence/
prompt-04-signal-integration/
prompt-05-workstream-context/
prompt-06-obsidian-provenance/
prompt-07-morning-orchestration/
prompt-08-ci-evidence/
final-closeout/
```

## Required Final Validation

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src
.venv/bin/hb-assistant diagnostics paths --json
.venv/bin/hb-assistant diagnostics env --json
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant actions extract --dry-run --json
.venv/bin/hb-assistant actions list --json
.venv/bin/hb-assistant search "waiting on" --json
.venv/bin/hb-assistant files sample --json
.venv/bin/hb-assistant files ingest --dry-run --json
.venv/bin/hb-assistant run morning --dry-run --json
```

## Evidence Acceptance Rules

- Evidence must be sanitized.
- Evidence must state whether commands were freshly run or evidence-based.
- Evidence must not include full bodies, full file contents, tokens, secrets, or private keys.
- Evidence must include final commit SHA.
- Evidence must classify delegated Graph proof as deferred until admin consent is granted.
