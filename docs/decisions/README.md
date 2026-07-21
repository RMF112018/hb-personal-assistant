# Repository Decision Records

This directory contains repository-canonical architectural and engineering
decision records for `RMF112018/hb-personal-assistant`.

## Authority

- Current repository implementation, configuration, tests, and runtime evidence
  remain higher authority than a decision record when they conflict.
- Accepted ADRs and operator decisions govern future implementation until
  superseded.
- Proposed ADRs do not authorize implementation, deletion, merge, deployment,
  production activation, or risk acceptance.
- Google Drive copies are publication/reference artifacts and must link back to
  the canonical repository decision and relevant GitHub issue, pull request, and
  SHA.

## Architectural Decisions

| ADR | Status | Decision |
|---|---|---|
| [`ADR-019`](ADR-019-github-first-engineering-control-plane.md) | Proposed | Make GitHub/repository canonical for engineering execution, retain Google Drive as publication/reference, and require governed branch/worktree closeout |

## Operator Decisions

| Decision | Status | Scope |
|---|---|---|
| [`DECISION-PROPORTIONAL-TEST-SELECTION-001`](DECISION-PROPORTIONAL-TEST-SELECTION-001.md) | Accepted | Require proportional test selection, evidence-based failure classification, separately authorized parallel correction, and zero unresolved required-suite failures at merge readiness |

## Related Policies and Standards

- [`POL-GIT-HYGIENE-001`](../governance/branch-worktree-lifecycle-policy.md)
  operationalizes branch/worktree registration, preservation, cleanup,
  retention, and closeout receipts under ADR-019.
- [`11_REPOSITORY_TEST_SELECTION_STANDARD`](../../.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md)
  operationalizes proportional test selection, failure disposition, parallel
  corrective-work constraints, and the no-known-failure integration rule.

## Lifecycle

Use the applicable AEOS template under `.ai/templates/aeos-core/`.
Preserve supersession history and review the exact pull-request head before
accepting a decision.
