# Prompt 07 — MVP Operator Runbook and Known Limitations

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Create operator-facing documentation so Bobby can run, inspect, and troubleshoot the local MVP without reading code.

## Required Files

Create or update:

```text
docs/operations/mvp-local-runtime-operator-guide.md
docs/evidence/mvp-local-runtime/07-operator-runbook-and-limitations.md
docs/evidence/mvp-local-runtime/06-known-limitations.md
```

## Operator Guide Must Include

- How to activate venv.
- How to run diagnostics.
- How to run morning dry-run.
- How to run apply/write mode, if supported.
- What gets written locally.
- What never gets written.
- Where logs/evidence live.
- Where SQLite/auth/cache files live.
- How to disable launchd.
- How to inspect errors.
- What remains blocked by IT/admin consent.
- How to run Prompt 9 after consent is granted.

## Commit Message

```text
docs(operations): add MVP local runtime operator guide
```
