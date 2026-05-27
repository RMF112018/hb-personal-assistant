# Prompt 02 — Dry-Run Semantics and Run Ledger Policy

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Make dry-run behavior truthful, documented, and tested.

## Required Policy

```text
Dry-run does not mutate Microsoft 365, Obsidian notes, action_items, source_records, source_links, files, parser_outputs, or generated work products.

Dry-run may write local run-ledger/evidence records when explicitly documented.
```

## Required Patch

- Align CLI notes with actual behavior.
- If dry-run writes run ledger/evidence, document it explicitly.
- Ensure dry-run does not write business objects.
- Add tests proving no `action_items` / `source_links` / Obsidian writes in dry-run.

## Evidence

Create:

```text
docs/evidence/mvp-local-runtime/02-dry-run-policy-proof.md
```

## Commit Message

```text
docs(runtime): clarify and prove dry-run mutation policy
```
