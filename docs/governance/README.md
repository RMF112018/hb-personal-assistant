# Repository Governance Policies

This directory contains repository-canonical policies and procedures that
operationalize accepted architectural decisions and AEOS requirements for
`RMF112018/hb-personal-assistant`.

## Authority

- Current implementation, tests, configuration, and runtime evidence remain
  higher authority when they conflict with a policy claim.
- Accepted policies govern future work until superseded.
- Proposed or review-pending policies do not authorize implementation, deletion,
  merge, deployment, production activation, or risk acceptance.
- Drive copies are publication/reference artifacts and identify canonical paths
  and source identities.

## Index

| Artifact | Status | Purpose |
|---|---|---|
| [`POL-GIT-HYGIENE-001`](branch-worktree-lifecycle-policy.md) | Accepted — Phase A | Branch/worktree identity, preservation, cleanup, retention, and closeout |
| [Test Failure Triage](test-failure-triage.md) | Normative procedure under Standard 11 | Durable failure ID, owner, evidence, authorization state, and closure |

POL-GIT-HYGIENE-001 acceptance is bound to PR #318 independent approval of head
`3abddb08751c702fdd73e54e3a0b9e9543099059` and operator-authorized merge commit
`8b44cbd216d531a1894b4257355469edf922029f`. Phase B and cleanup remain
separately authorized activities.

## Lifecycle

Materially changed policies require exact-head independent review. Preserve
change, acceptance, and supersession history. Review, operator acceptance,
merge, cleanup, deployment, and risk acceptance remain distinct.
