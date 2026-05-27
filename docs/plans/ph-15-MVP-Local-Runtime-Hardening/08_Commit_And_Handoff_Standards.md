# 08 — Commit and Handoff Standards

## Commit Discipline

- One logical commit per prompt unless a prompt explicitly spans multiple commits.
- Commit only intentional source/docs/evidence changes.
- Do not commit local DBs, tokens, cache files, PEMs, raw emails, raw files, or private Obsidian content.

## Example Commit Message

```text
feat(mvp-runtime): harden local morning action extraction

- Verify repo truth at baac7b5...
- Patch run morning action extraction stage
- Add seeded fixture proof and idempotency test
- Capture redacted evidence under docs/evidence/mvp-local-runtime
```

## Required Final Handoff

Each prompt closeout must include:

```text
## Starting State
- Branch:
- Starting HEAD:
- Working tree:

## Changes Made
- Files changed:
- Key behavior changed:

## Validation
- Command:
- Exit code:
- Output path:

## Evidence
- Evidence files:

## Risks / Deferred
- Remaining risks:
- Deferred Graph proof status:

## Final State
- Final HEAD:
- Working tree:
```

## Final MVP Closeout

Final closeout must state one of:

```text
MVP_CANDIDATE_LOCAL_RUNTIME_READY
MVP_CANDIDATE_WITH_LOCAL_GAPS
LOCAL_RUNTIME_BLOCKED
```

And separately:

```text
GRAPH_DELEGATED_PROOF_DEFERRED_PENDING_ADMIN_CONSENT
```
