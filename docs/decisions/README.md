# Repository Decision Records

This directory contains repository-canonical architectural and engineering
decision records for `RMF112018/hb-personal-assistant`.

## Authority

- Current repository implementation, configuration, tests, and runtime evidence
  remain higher authority than a decision record when they conflict.
- Accepted ADRs and accepted operator decisions govern future implementation
  until superseded.
- Proposed, review-pending, or changes-requested records do not authorize
  implementation, deletion, merge, deployment, production activation, or risk
  acceptance.
- Review, operator acceptance, merge, and effectiveness are distinct states.
- Google Drive copies are publication/reference artifacts and link back to the
  canonical repository decision, PR, and SHA.

## Architectural decisions

| ADR | Status | Decision |
|---|---|---|
| [`ADR-019`](ADR-019-github-first-engineering-control-plane.md) | Accepted — Phase A | GitHub/repository are engineering execution authority; Drive is publication/reference; branch/worktree closeout is governed |

ADR-019 acceptance evidence is PR #318 independent approval of exact head
`3abddb08751c702fdd73e54e3a0b9e9543099059` and operator-authorized squash merge
at `8b44cbd216d531a1894b4257355469edf922029f`. Phase B remains separately
unauthorized.

## Operator decision candidates

| Decision | Status | Scope |
|---|---|---|
| [`DECISION-PROPORTIONAL-TEST-SELECTION-001`](DECISION-PROPORTIONAL-TEST-SELECTION-001.md) | Review Pending — Corrective Revision | Proportional tests, durable failure ownership, separate correction, and no-known-failure merge gate |

The proportional-testing decision is not accepted until a fresh exact-head
independent review passes and the operator separately accepts that reviewed
head.

## Related policies and standards

- [`POL-GIT-HYGIENE-001`](../governance/branch-worktree-lifecycle-policy.md) —
  Accepted — Phase A; governs branch/worktree registration, preservation,
  cleanup, retention, and closeout.
- [`07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT`](../../.ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md) — local implementation contract.
- [`11_REPOSITORY_TEST_SELECTION_STANDARD`](../../.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md) — proportional selection, failure ownership, parallel correction, and merge-safe gate.

## Lifecycle

Use the applicable AEOS template. Preserve supersession and review history.
Independent review identifies the exact PR head. Operator acceptance is a
separate durable record and does not by itself merge, deploy, clean up, or accept
risk.
