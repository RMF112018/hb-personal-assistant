# Repository Governance Policies

This directory contains repository-canonical policies that operationalize
accepted architectural decisions and AEOS requirements for
`RMF112018/hb-personal-assistant`.

## Authority

- Current repository implementation, tests, configuration, and runtime evidence
  remain higher authority when they conflict with a policy claim.
- Accepted policies govern future repository work until superseded.
- Proposed policies do not authorize implementation, deletion, merge,
  deployment, production activation, or risk acceptance.
- Google Drive copies are publication/reference artifacts and must identify the
  canonical repository path and source commit.

## Index

| Policy | Status | Purpose |
|---|---|---|
| [`POL-GIT-HYGIENE-001`](branch-worktree-lifecycle-policy.md) | Proposed | Govern branch/worktree registration, preservation, cleanup, retention, and closeout receipts |

## Lifecycle

Policies require exact-head independent review as part of the pull request that
introduces or materially changes them. Preserve change and supersession history.
