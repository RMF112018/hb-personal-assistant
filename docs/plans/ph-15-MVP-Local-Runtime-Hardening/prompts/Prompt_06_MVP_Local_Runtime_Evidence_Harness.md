# Prompt 06 — MVP Local Runtime Evidence Harness

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Create a deterministic evidence harness that proves the local-first assistant loop works without Graph consent.

## Required Capabilities

The harness should seed or use safe fixtures for:

- redacted body mention;
- waiting-on signal;
- action candidate;
- parser excerpt;
- file review candidate;
- upcoming calendar item;
- source links;
- existing note content outside managed markers.

## Required Proofs

1. `actions extract --dry-run --json`
2. `actions list --json`
3. `run morning --dry-run --json`
4. Obsidian marker-bound proof
5. Idempotency proof over two identical runs
6. Sensitive scan proof

## Evidence Tree

Create:

```text
docs/evidence/mvp-local-runtime/06-local-runtime-evidence-harness.md
docs/evidence/mvp-local-runtime/outputs/actions-extract-dry-run.json
docs/evidence/mvp-local-runtime/outputs/actions-list.json
docs/evidence/mvp-local-runtime/outputs/run-morning-dry-run.json
docs/evidence/mvp-local-runtime/outputs/idempotency-proof.json
docs/evidence/mvp-local-runtime/outputs/scan-sensitive.json
```

## Commit Message

```text
test(mvp-runtime): add deterministic local runtime evidence harness
```
