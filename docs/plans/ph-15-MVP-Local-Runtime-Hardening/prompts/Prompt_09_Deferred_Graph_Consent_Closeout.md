# Prompt 09 — Deferred Graph Consent Closeout

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Execute Only After IT/Admin Consent Is Granted

Do not execute this prompt until Microsoft Graph delegated permissions/admin consent are available.

## Objective

Close the deferred delegated Graph proof and update final acceptance posture.

## Required Commands

```bash
git status --short
git rev-parse HEAD

.venv/bin/hb-assistant auth clear-cache --json
.venv/bin/hb-assistant auth login --json
.venv/bin/hb-assistant auth status --json
.venv/bin/hb-assistant diagnostics graph --safe --json
.venv/bin/hb-assistant diagnostics proof delegated-graph --json
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
```

## Evidence

Create:

```text
docs/evidence/graph-delegated-proof-closeout/
  00-preflight.md
  01-auth-login-redacted.json
  02-auth-status.json
  03-diagnostics-graph-safe.json
  04-delegated-graph-proof.json
  05-sensitive-scan.json
  06-final-graph-closeout.md
```

## Acceptance

- Delegated user token confirmed.
- No app-only runtime mail/calendar.
- Mail/calendar/drive proof succeeds.
- Bounded body/file proof succeeds within safety gates.
- Sensitive scan clean.
- README/architecture updated from deferred to closed.

## Commit Message

```text
chore(graph): close delegated proof after admin consent
```
