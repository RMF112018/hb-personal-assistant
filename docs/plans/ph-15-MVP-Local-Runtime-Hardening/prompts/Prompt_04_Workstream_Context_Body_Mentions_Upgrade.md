# Prompt 04 — Workstream Context Body Mentions Upgrade

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Make body mentions first-class in `WorkstreamContextBuilder`, not just indirectly available to the brief generator.

## Required Patch

Update `WorkstreamContextBuilder.build_for_today()` so `mentions` is populated from bounded store helpers, preferably:

```python
mentions = self.store.list_recent_body_mentions(limit=limit_per)
```

Bound/redact fields before returning context.

## Tests

Add tests proving:

- empty store returns empty mentions cleanly;
- seeded body mention appears in context;
- no full body content appears in context;
- brief generation can consume context mentions.

## Evidence

Create:

```text
docs/evidence/mvp-local-runtime/04-workstream-context-mentions-proof.md
```

## Commit Message

```text
feat(context): include body mentions in workstream context
```
