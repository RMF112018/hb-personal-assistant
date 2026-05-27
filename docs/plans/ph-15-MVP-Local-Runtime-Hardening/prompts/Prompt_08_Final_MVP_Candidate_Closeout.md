# Prompt 08 — Final MVP Candidate Closeout

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Run the final validation matrix and produce a truthful MVP candidate closeout.

## Required Commands

```bash
git status --short
git rev-parse HEAD

.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src

.venv/bin/hb-assistant --version
.venv/bin/hb-assistant diagnostics env --json
.venv/bin/hb-assistant diagnostics paths --json
.venv/bin/hb-assistant diagnostics automation --json
.venv/bin/hb-assistant actions extract --dry-run --json
.venv/bin/hb-assistant actions list --json
.venv/bin/hb-assistant run morning --dry-run --json
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
```

## Required Closeout File

Create:

```text
docs/evidence/mvp-local-runtime/08-final-mvp-candidate-closeout.md
```

## Required Final Classification

Use one of:

```text
MVP_CANDIDATE_LOCAL_RUNTIME_READY
MVP_CANDIDATE_WITH_LOCAL_GAPS
LOCAL_RUNTIME_BLOCKED
```

And separately:

```text
GRAPH_DELEGATED_PROOF_DEFERRED_PENDING_ADMIN_CONSENT
```

## Commit Message

```text
chore(mvp-runtime): close local MVP candidate hardening phase
```
