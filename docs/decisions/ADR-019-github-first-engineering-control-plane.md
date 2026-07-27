---
title: "GitHub-First Engineering Control Plane"
artifact_id: "ADR-019"
classification: "ADRs"
artifact_type: "Architectural Decision Record"
version: "1.0"
status: "Accepted — Phase A"
date_created: "2026-07-21"
date_updated: "2026-07-21"
decision_owner: "Bobby Fetting"
author: "OpenAI ChatGPT, operator-directed"
repository: "RMF112018/hb-personal-assistant"
branch_pr_commit: "chore/github-first-control-plane-phase-a / PR #318 / merge 8b44cbd216d531a1894b4257355469edf922029f"
decision_scope: "Multi-agent engineering authority, exact-SHA review, repository hygiene, and Drive publication boundaries"
accepted_review:
  pull_request: 318
  base_sha: "e30c63846f36f7fa59b7784c2f345d8483a566f9"
  reviewed_head_sha: "3abddb08751c702fdd73e54e3a0b9e9543099059"
  disposition: "APPROVE"
  review_record: "PR #318 operator-posted independent review comment"
operator_acceptance:
  action: "Exact-head squash merge"
  merge_commit: "8b44cbd216d531a1894b4257355469edf922029f"
  merged_at: "2026-07-21T09:21:31Z"
phase_b_authorized: false
supersedes: []
superseded_by: []
related_artifacts:
  - "GitHub issue #317"
  - "GitHub PR #318"
  - "AGENTS.md"
  - "AI_OPERATING_MANUAL.md"
  - "CLAUDE.md"
  - "docs/governance/branch-worktree-lifecycle-policy.md"
  - "docs/implementation-plans/github-first-control-plane-migration.md"
evidence_references:
  - "PR #318 exact-head independent review"
  - "PR #318 merge commit 8b44cbd216d531a1894b4257355469edf922029f"
  - "Google Drive Workspace 17fLunEr0ZGC_zsYCJn3x9v2I6gYuxKHZ"
tags: [aeos, adr, architecture, github, multi-agent, control-plane, repository-hygiene]
---

# GitHub-First Engineering Control Plane

**Classification:** ADRs  
**Version:** 1.0  
**Status:** Accepted — Phase A

## Decision summary

For `RMF112018/hb-personal-assistant`, GitHub and the repository are the
canonical engineering execution control plane. Deployed runtime evidence is
canonical for operational behavior. Google Drive remains the publication,
collaboration, reference, and external-handoff surface. Final lifecycle,
merge, deployment, production, and risk decisions remain with the operator.

Branches and linked worktrees are governed execution records. A merged pull
request transitions associated work to `MERGED_PENDING_CLEANUP`; it does not
close the work item until all branch/worktree dispositions are verified and
evidenced.

## Context

The prior model represented active engineering state across Drive documents,
repository goal records, branches, worktrees, PRs, and session handoffs. This
created split authority, stale SHA pointers, repeated synchronization, and
abandoned local execution state. The migration preserves AEOS controls and
historical Drive evidence while moving mutable execution identity to the system
that enforces code review and merge.

## Decision drivers

- Bind implementation and review to exact repository identities.
- Make current goal, branch, PR, review, and lifecycle state queryable.
- Preserve operator authorization and implementer/reviewer separation.
- Preserve Drive history and cross-platform publication.
- Require every branch and worktree to have ownership and disposition.
- Prevent dirty, unique, inaccessible, locked, or process-dependent work from
  being destroyed during cleanup.
- Support all approved agent harnesses through common canonical governance.

## Scope

### In scope

- Engineering, runtime, publication/reference, and final-decision authority.
- Goal, work-item, authorization, branch, SHA, PR, review, and checkpoint identity.
- Branch/worktree registration, lifecycle, preservation, cleanup, and receipts.
- Migration phases and acceptance gates.
- Generated or linked Drive publication.

### Out of scope

- Application runtime behavior.
- Deployment, production activation, database or data migration.
- Credential or secret changes.
- Phase B pilot activation.
- Destructive cleanup of existing branches/worktrees during Phase A.
- Deletion or relocation of historical Workspace artifacts.

## Decision

The adopted authority model is:

1. **Engineering execution authority** — repository and GitHub issues, branches,
   commits, pull requests, reviews, required checks, and governed local records.
2. **Runtime authority** — deployed environments and runtime-generated evidence.
3. **Publication/reference authority** — Google Drive Software Delivery Control
   Center and other approved publication surfaces.
4. **Final decision authority** — the operator.

For repository-specific work:

- repository/GitHub define active goal, work item, authorization, branch, base
  and head SHAs, PR, review status, merge state, checkpoint, and lifecycle;
- independent review identifies the exact reviewed head; a changed head invalidates
  current-head approval unless an accepted policy defines a narrower result;
- Drive copies and summaries point to canonical repository/GitHub identities and
  cannot independently authorize execution;
- historical Drive records remain preserved;
- new Drive-native mechanisms that independently track active engineering state
  remain frozen during migration.

For branches and worktrees:

- every non-canonical entity is registered before substantive work;
- branch and worktree identities remain distinct;
- current branch tips and exact review candidates are resolved from authenticated
  GitHub/local Git rather than self-referential in-commit claims;
- merge moves work to `MERGED_PENDING_CLEANUP`, not `CLOSED`;
- worktree removal, local branch deletion, remote deletion, metadata pruning, and
  remote-reference pruning are separate governed actions;
- uncertain state fails closed to preservation;
- forceful cleanup is exceptional and requires explicit operator authority,
  preservation evidence, and recovery evidence.

The governing lifecycle contract is
`docs/governance/branch-worktree-lifecycle-policy.md`.

## Alternatives

### Retain Drive-first orchestration

Rejected because it preserves split authority, manual synchronization, stale SHA
risk, and weak local cleanup governance.

### GitHub-only

Rejected for the current migration because Drive remains useful for long-form,
cross-platform publication and external handoff.

### GitHub-first hybrid

Selected because it binds execution and review to repository identities while
preserving Drive publication and AEOS controls.

## Architectural invariants

1. Repository/runtime evidence outranks summaries and copied publications.
2. Only the operator may accept risk, authorize merge, exceptional destructive
   cleanup, deployment, or production activation.
3. Implementers do not independently approve or audit their own implementation.
4. Active engineering state has one canonical repository/GitHub identity.
5. Review is traceable to an exact SHA.
6. Every non-canonical branch/worktree has identity, owner, lifecycle state, and
   disposition.
7. Merge does not equal closeout.
8. Dirty or uniquely committed work is preserved until reconciled.
9. Historical Drive records are preserved during migration.
10. Publication cannot override repository execution state.

## Failure behavior

- Conflicting Drive and repository execution state fails closed to repository and
  GitHub truth.
- Missing or stale reviewed-SHA evidence blocks approval claims.
- Publication failure does not mutate canonical engineering state.
- Failed reconciliation prevents lifecycle advancement.
- Dirty, unique, uncertain, locked, inaccessible, or process-used state blocks
  deletion.
- Cleanup failures remain `CLEANUP_BLOCKED` or `MERGED_PENDING_CLEANUP`.

## Migration phases

- **Phase A:** authority decision, Drive-state freeze, lifecycle policy — accepted.
- **Phase B:** pilot the permanent-identity goal and full cleanup lifecycle — not
  authorized by this ADR or its Phase A acceptance.
- **Phase C:** semantic validation, enforcement, registry, and reconciliation.
- **Phase D:** Drive consolidation and generated publication.
- **Phase E:** cross-harness conformance validation.

## Risks

| Risk | Mitigation |
|---|---|
| Split authority persists during transition | Explicit authority order and phase gates |
| Reviews become stale | Exact-head binding and stale-head invalidation |
| Harnesses resolve different state | Canonical entrypoints and Phase E conformance |
| Historical Drive evidence is overwritten | Stable-ID preservation and no Phase A relocation |
| Dirty or unique work is deleted | Fail-closed lifecycle and preservation proof |
| Merged entities accumulate | `MERGED_PENDING_CLEANUP`, registry, and receipts |
| Remote deletion exceeds authority | Separate remote disposition and exact authorization |

## Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| `AC-GHCP-A-001` | Four authority categories are explicit | This ADR |
| `AC-GHCP-A-002` | Root governance routes execution to repository/GitHub | `AGENTS.md`, `AI_OPERATING_MANUAL.md`, `CLAUDE.md` |
| `AC-GHCP-A-003` | Drive is publication/reference and preserves history | Workspace operating controls |
| `AC-GHCP-A-004` | Branch/worktree lifecycle and fail-closed cleanup are defined | `POL-GIT-HYGIENE-001` |
| `AC-GHCP-A-005` | PR #318 received exact-head independent approval | Reviewed head `3abddb...` record |
| `AC-GHCP-A-006` | Operator accepted Phase A through exact-head merge | Main commit `8b44cbd...` |
| `AC-GHCP-A-007` | Phase B and destructive cleanup remain separately unauthorized | This ADR and migration plan |

## Acceptance record and boundary

A fresh independent review of PR #318 head
`3abddb08751c702fdd73e54e3a0b9e9543099059` returned `APPROVE`. The operator then
authorized and completed an exact-head squash merge at main commit
`8b44cbd216d531a1894b4257355469edf922029f` on 2026-07-21.

This record accepts Phase A only. It does not authorize Phase B, cleanup,
deployment, migration, production activation, or risk acceptance.

## Residual work

Phases B–E remain unimplemented or incomplete. Existing branches and worktrees
have not all been reconciled under the lifecycle policy. Required checks,
registry automation, and cleanup tooling remain future governed work.
