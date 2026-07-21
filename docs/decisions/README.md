# Repository Decision Records

This directory contains repository-canonical architectural and engineering
decision records for `RMF112018/hb-personal-assistant`.

## Authority

- Current repository implementation, configuration, tests, and runtime evidence
  remain higher authority than a decision record when they conflict.
- Accepted ADRs govern future implementation until superseded.
- Proposed ADRs do not authorize implementation, deletion, merge, deployment,
  production activation, or risk acceptance.
- Google Drive copies are publication/reference artifacts and must link back to
  the canonical repository ADR and relevant GitHub issue, pull request, and SHA.

## Index

| ADR | Status | Decision |
|---|---|---|
| [`ADR-019`](ADR-019-github-first-engineering-control-plane.md) | Proposed | Make GitHub/repository canonical for engineering execution, retain Google Drive as publication/reference, and require governed branch/worktree closeout |

## Related Policies

- [`POL-GIT-HYGIENE-001`](../governance/branch-worktree-lifecycle-policy.md)
  operationalizes branch/worktree registration, preservation, cleanup,
  retention, and closeout receipts under ADR-019.

## Lifecycle

Use the AEOS ADR template under `.ai/templates/aeos-core/ADRs-template.md`.
Preserve supersession history and review the exact pull-request head before
accepting a decision.
