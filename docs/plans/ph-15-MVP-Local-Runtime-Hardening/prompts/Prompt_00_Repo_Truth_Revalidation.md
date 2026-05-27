# Prompt 00 — Repo-Truth Revalidation

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Prove the exact repository, branch, commit, working tree, and Phase 14 state before any hardening patches.

## Required Commands

```bash
git remote -v
git branch --show-current
git rev-parse HEAD
git log --oneline -20
git status --short
```

## Required Inspections

```bash
grep -R "CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER" -n README.md docs || true
grep -R "DNS" -n README.md docs/evidence/phase-14-local-runtime-workstream-intelligence docs/architecture || true
grep -R "Phase 14 Prompt" -n docs/architecture docs/evidence | head -100 || true
find docs/evidence/phase-14-local-runtime-workstream-intelligence -maxdepth 4 -type f | sort || true
```

## Deliverable

Create:

```text
docs/evidence/mvp-local-runtime/00-repo-truth.md
```

## Acceptance

- Correct repo confirmed.
- Exact HEAD confirmed or deviation documented.
- Graph blocker classified as admin consent pending, not DNS, unless current command evidence proves DNS.
