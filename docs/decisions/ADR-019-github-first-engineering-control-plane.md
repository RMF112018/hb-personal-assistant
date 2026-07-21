---
title: "GitHub-First Engineering Control Plane"
artifact_id: "ADR-019"
classification: "ADRs"
artifact_type: "Architectural Decision Record"
version: "0.2"
status: "Proposed"
date_created: "2026-07-21"
date_updated: "2026-07-21"
decision_owner: "Bobby Fetting"
author: "OpenAI ChatGPT, operator-directed"
repository: "RMF112018/hb-personal-assistant"
branch_pr_commit: "chore/github-first-control-plane-phase-a / PR #318"
decision_scope: "Multi-agent software-delivery governance, execution state, review evidence, repository hygiene, and Google Drive publication"
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
  - "Google Drive Workspace 17fLunEr0ZGC_zsYCJn3x9v2I6gYuxKHZ"
  - "Repository main at e30c63846f36f7fa59b7784c2f345d8483a566f9"
tags:
  - aeos
  - adr
  - architecture
  - github
  - multi-agent
  - control-plane
  - repository-hygiene
  - worktree
  - branch
---

# GitHub-First Engineering Control Plane

**Classification:** ADRs  
**Artifact Type:** Architectural Decision Record  
**Version:** 0.2  
**Status:** Proposed

## Decision Summary

For `RMF112018/hb-personal-assistant`, GitHub and the repository will become the
canonical engineering execution control plane. Google Drive will remain a
cross-platform collaboration, publication, and reference surface, but it will
not independently define active engineering state.

Branches and linked worktrees are governed execution records. A merged pull
request transitions its associated work to `MERGED_PENDING_CLEANUP`; it does not
make the work item complete until branch and worktree disposition is verified
and recorded.

## Context

The current Software Delivery Control Center uses Google Drive for governance,
plans, goals, reviews, audits, evidence, decisions, current-state ledgers, and
handoffs. The repository separately contains AEOS governance, agent skills,
goal-control structures, branches, commits, pull requests, tests, and
implementation evidence.

The current model has strong governance but produces split authority and
repeated manual synchronization. Active state can be represented in Drive
documents, repository goal records, local worktrees, branches, pull requests,
and model handoffs. Review conclusions are often transported into pull-request
descriptions rather than being bound to the exact reviewed pull-request head.

Local execution has an additional control gap: agents frequently create
branches and worktrees but treat merge or handoff as completion. Stale
worktrees, local branches, and remote branches then accumulate. This obscures
repository truth, retains unknown unique commits, consumes local resources, and
increases the chance that a later agent operates from the wrong checkout or
baseline.

The migration must preserve existing AEOS controls and historical Drive records
while reducing duplicated state, stale context, manually transcribed review
evidence, and unmanaged repository-local execution state.

## Decision Drivers

- Bind implementation and independent review to exact repository identities.
- Make current engineering state deterministically queryable.
- Reduce repeated manual updates across multiple Drive ledgers.
- Preserve the existing cross-platform Drive Workspace and historical evidence.
- Keep operator authorization and implementer/reviewer separation intact.
- Ensure every branch and worktree has an owner, purpose, and final disposition.
- Prevent dirty or uniquely committed work from being destroyed during cleanup.
- Support Claude Code, Codex, Grok, Composer, ChatGPT, and future approved
  harnesses.

## Scope

### In Scope

- Engineering authority hierarchy.
- Goal, work-item, authorization, branch, commit, pull-request, review, and
  checkpoint identity.
- Branch and worktree registration, lifecycle, preservation, cleanup, and
  closeout evidence.
- Local and remote branch disposition.
- Repository and Drive governance language.
- Migration phases and completion gates.
- Generated publication of human-readable Workspace summaries.

### Out of Scope

- Application runtime behavior.
- Production deployment or activation.
- Database or data migration.
- Credential or secret changes.
- Immediate conversion of the active permanent-identity goal.
- Destructive cleanup of existing branches or worktrees during Phase A.
- Deletion or relocation of historical Workspace artifacts.

## Decision

The following authority model is adopted:

1. **Engineering execution authority** — the repository and GitHub issue,
   branch, commit, pull-request, review, required-check, and governed local
   worktree records.
2. **Runtime authority** — the deployed environment and runtime-generated
   evidence for operational claims.
3. **Publication and reference authority** — the Google Drive Software Delivery
   Control Center.
4. **Final decision authority** — the operator.

For repository-specific work:

- GitHub and repository records define active goal identity, work item,
  authorization pointer, branch, base SHA, head SHA, pull request, review status,
  merge readiness, checkpoint identity, and branch/worktree lifecycle state.
- Independent review must identify the exact pull-request head SHA it reviewed.
  A changed head invalidates the previous current-head review unless the
  governing policy explicitly defines a narrower non-stale result.
- Drive may publish copies, summaries, review packages, and external handoffs,
  but Drive content must point to the canonical GitHub or repository record.
- Drive file access, Workspace selection, or a Drive-native state change does
  not authorize repository action.
- Existing Drive artifacts remain preserved as historical evidence and are not
  retroactively reclassified or deleted by this decision.
- New Drive-native mechanisms that independently track active engineering
  execution state are frozen during migration.

For branches and worktrees:

- Every non-canonical worktree must be registered to a governed work item before
  substantive editing.
- Registration must identify its path, branch, base SHA, owner or agent, goal or
  work item, associated issue or pull request when available, and expected
  disposition.
- A pull-request merge changes the lifecycle state to
  `MERGED_PENDING_CLEANUP`, not directly to `CLOSED`.
- Work-item closure requires verified disposition of the worktree, local branch,
  and remote branch, plus a cleanup, retention, or blocker receipt.
- Dirty worktrees, unique commits, uncertain patch equivalence, or active
  processes fail closed to preservation.
- Local worktree removal, local branch deletion, and remote branch deletion are
  separate governed actions.
- Forceful cleanup is exceptional and requires explicit operator authorization,
  preservation evidence, and a recovery receipt.
- The governing lifecycle contract is
  `docs/governance/branch-worktree-lifecycle-policy.md`.

## Alternatives Considered

### Alternative A — Retain Drive-First Orchestration

**Description:** Keep Drive as the canonical Workspace and continue manually
synchronizing repository state.  
**Advantages:** Familiar cross-platform access; readable long-form documents.  
**Disadvantages:** Split authority, duplicated ledgers, weak SHA binding,
growing context cost, manual drift risk, and no enforceable local cleanup
lifecycle.  
**Disposition:** Rejected.

### Alternative B — GitHub-Only

**Description:** Remove Drive from the governed workflow and store all material
in GitHub.  
**Advantages:** Single engineering system of record and strong commit binding.  
**Disadvantages:** Reduced convenience for external, long-form, and
cross-platform publication; discards a useful collaboration surface.  
**Disposition:** Rejected for the current migration.

### Alternative C — GitHub-First Hybrid with Governed Repository Hygiene

**Description:** Make GitHub/repository canonical for engineering execution,
retain Drive as generated publication/reference, and make branch/worktree
closeout part of the work-item lifecycle.  
**Advantages:** Strong identity binding, lower duplication, deterministic
cleanup eligibility, preservation of unique work, and retained cross-platform
access.  
**Disadvantages:** Requires migration tooling, a local registry, semantic
validation, and temporary transition work.  
**Disposition:** Selected.

## Rationale

Engineering state is most trustworthy when it is bound to the same branch,
commit, pull request, checks, and merge controls that govern the code. Drive
remains valuable for human-readable publication and cross-model retrieval, but
it should not duplicate mutable engineering state that GitHub already
represents more precisely.

The local worktree is part of execution state because it may contain dirty
files, untracked artifacts, running services, unique commits, or evidence that
is not represented by the pull request. Therefore, merge cannot be treated as
complete closeout. A deterministic lifecycle and receipt are required to prove
that the local and remote repository state has been safely reconciled.

This decision retains AEOS governance, human authorization, independent review,
durable evidence, and bounded state transitions while moving execution
identity to the system that can enforce it.

## Consequences

### Positive

- Reviews can be bound to exact pull-request heads.
- Branch, SHA, work-item, merge, and cleanup state become directly queryable.
- Drive context can be smaller and generated.
- Manual triple-entry ledger updates can be retired.
- Existing Workspace investment and historical records are preserved.
- Agents can no longer silently abandon worktrees after merge.
- Unique or dirty work blocks deletion rather than being destroyed.
- A cleanup receipt creates recovery and audit evidence.

### Negative

- Migration phases require repository, GitHub, Drive, harness, and local tooling
  changes.
- Some participating models may require adapter work for reliable GitHub
  retrieval.
- The transition temporarily retains both old and new representations.
- Closeout requires an additional explicit lifecycle checkpoint.

### Neutral

- Operator authorization remains mandatory.
- Merge, cleanup, deployment, production, and operational readiness remain
  separate decisions.
- Drive remains an approved source for governance publication and external
  review packages.

## Architectural Invariants

1. Repository and runtime evidence outrank summaries, model memory, and copied
   publication artifacts.
2. The operator is the only authority for risk acceptance, lifecycle
   authorization, merge, exceptional destructive cleanup, deployment, and
   production activation.
3. Implementers do not independently approve or audit their own implementation.
4. Active engineering state has one canonical repository/GitHub identity.
5. Review status is traceable to an exact reviewed SHA.
6. Every non-canonical branch and worktree has a governed identity and
   disposition.
7. Merge does not equal closeout; cleanup or retention must be verified.
8. Dirty or uniquely committed work is preserved until safely reconciled.
9. Historical Drive records are preserved during migration.
10. Drive publication cannot silently override repository engineering state.

## Security and Trust Boundaries

- GitHub write authority does not imply deployment or production authority.
- Drive write authority does not imply repository action authority.
- Branch creation authority does not imply branch or worktree deletion authority.
- Local cleanup authority does not imply remote branch deletion authority.
- A model-generated review is a claim until its identity, inputs, reviewed SHA,
  evidence, and disposition are durably recorded.
- Credentials, secrets, tokens, and sensitive runtime or process evidence remain
  excluded from governance publications and cleanup receipts.

## Failure Behavior

- Conflicting Drive and repository execution state fails closed to
  repository/GitHub truth and must be reported.
- Missing or stale reviewed-SHA evidence blocks a current-head independent-review
  claim.
- Failed publication to Drive does not change canonical repository state.
- Failed GitHub state reconciliation prevents automated lifecycle advancement.
- Dirty state, unique commits, uncertain integration proof, or active process
  use blocks worktree deletion.
- Refusal by `git branch -d` is a preservation signal, not permission to use
  `git branch -D`.
- Cleanup failures leave the work item in `CLEANUP_BLOCKED` or
  `MERGED_PENDING_CLEANUP`; they do not silently advance to closure.

## Compatibility and Migration

Migration is executed through five phases:

- Phase A — authority decision, Drive-state freeze, and branch/worktree policy.
- Phase B — pilot the active permanent-identity goal and full cleanup lifecycle.
- Phase C — semantic validation, merge enforcement, registry, and hygiene
  reconciliation tooling.
- Phase D — Drive ledger consolidation and generated control-plane/hygiene
  publication.
- Phase E — cross-harness lifecycle conformance validation.

The active `GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001` is reserved for
the Phase B pilot and is not modified by Phase A.

Phase A adopts policy only. It does not authorize deleting existing branches,
worktrees, or remote refs.

## Rollback or Forward-Recovery Strategy

Before Phase B, rollback consists of reverting the Phase A repository governance
commit and removing or superseding the non-canonical Drive notice. Existing
Drive data and local Git state are not changed destructively.

After Phase B begins, forward recovery is preferred: preserve generated events
and cleanup receipts, correct canonical pointers, and restore consistency
without deleting historical evidence or uncertain local work.

## Risks

| Risk ID | Severity | Description | Mitigation | Status |
|---|---|---|---|---|
| `RISK-GHCP-001` | High | Split authority continues during transition | Explicit phase gates and canonical pointers | Open |
| `RISK-GHCP-002` | High | Review claims are not bound to current PR head | Required reviewed-SHA record and later required check | Open |
| `RISK-GHCP-003` | Medium | Harnesses resolve different current state | Phase E conformance suite | Open |
| `RISK-GHCP-004` | Medium | Historical Drive evidence is accidentally overwritten | Preserve stable IDs; no Phase A deletion or relocation | Open |
| `RISK-GHCP-005` | Medium | GitHub becomes overloaded with long-form publication | Keep Drive as publication/reference layer | Open |
| `RISK-GHCP-006` | High | Dirty or uniquely committed work is deleted during cleanup | Fail-closed lifecycle policy and preservation proof | Open |
| `RISK-GHCP-007` | Medium | Merged branches and worktrees accumulate indefinitely | Merge-to-cleanup state transition, registry, dashboard, and receipts | Open |
| `RISK-GHCP-008` | Medium | Agent removes a worktree still used by a process | Required process-use check before removal | Open |
| `RISK-GHCP-009` | Medium | Remote branch deletion exceeds local cleanup authority | Separate remote disposition and explicit authorization | Open |

## Acceptance Criteria

| ID | Criterion | Verification Method |
|---|---|---|
| `AC-GHCP-A-001` | Repository ADR explicitly defines all four authority categories | Review this ADR |
| `AC-GHCP-A-002` | Root agent governance routes active execution state to repository/GitHub | Diff review of governance files |
| `AC-GHCP-A-003` | `CLAUDE.md` no longer falsely states there is no frontend or web service | Diff review against repository structure |
| `AC-GHCP-A-004` | Drive operating instructions freeze new Drive-native execution state | Read updated Workspace instructions |
| `AC-GHCP-A-005` | Existing Drive artifacts and active pilot goal remain unmodified by Phase A | Drive metadata and folder comparison |
| `AC-GHCP-A-006` | A reviewable GitHub issue and pull request track Phase A | GitHub issue #317 and PR #318 |
| `AC-GHCP-A-007` | No merge, deployment, production mutation, credential change, data migration, or Git cleanup occurs in Phase A | PR scope and evidence review |
| `AC-GHCP-A-008` | A formal branch/worktree lifecycle policy defines registration, merge-pending-cleanup, fail-closed deletion proof, and receipts | Review `POL-GIT-HYGIENE-001` |
| `AC-GHCP-A-009` | Root governance makes branch/worktree disposition part of work-item closeout | Review `AGENTS.md` and `AI_OPERATING_MANUAL.md` |
| `AC-GHCP-A-010` | Phase B through E explicitly implement and validate the hygiene lifecycle | Review migration plan |

## Approval Gates

- Independent review of the exact current Phase A pull-request head, including
  the branch/worktree lifecycle policy.
- Operator approval to merge the Phase A pull request.
- Separate authorization before Phase B modifies or maps the pilot goal or
  executes any cleanup.

## Open Questions

- Which GitHub status/check mechanism will represent independent model review in
  Phase C?
- Which GitHub Project fields will be adopted for goals and work items?
- Where will the canonical worktree registry and cleanup receipts live?
- What staleness threshold will trigger operator review without authorizing
  deletion?
- Will GitHub automatic head-branch deletion be enabled after merge, and which
  retained branches will be excluded?
- Which Drive summary documents will remain generated after Phase D?
- How will Composer participate in the Phase E conformance suite?

## Evidence Basis

- Live repository governance and structure at
  `e30c63846f36f7fa59b7784c2f345d8483a566f9`.
- Live Google Drive Workspace manifest, bootstrap, operating instructions, root
  folders, reviews, goals, and ADR folders inspected on 2026-07-21.
- GitHub issue #317 and PR #318.
- Operator-reported recurring local and remote branch/worktree accumulation.

---

## Document Control

| Field | Value |
|---|---|
| Artifact ID | `ADR-019` |
| Classification | `ADRs` |
| Artifact Type | `Architectural Decision Record` |
| Version | `0.2` |
| Status | `Proposed` |
| Owner | `Bobby Fetting` |
| Author | `OpenAI ChatGPT, operator-directed` |
| Created | `2026-07-21` |
| Last Updated | `2026-07-21` |
| Repository / Workspace | `RMF112018/hb-personal-assistant` and Software Delivery Control Center |
| Branch / PR / Commit | `chore/github-first-control-plane-phase-a` / PR #318 / current head required |
| Supersedes | None |
| Superseded By | None |

## Change Log

| Version | Date | Author | Change Summary |
|---|---|---|---|
| `0.1` | `2026-07-21` | OpenAI ChatGPT, operator-directed | Initial proposed authority decision |
| `0.2` | `2026-07-21` | OpenAI ChatGPT, operator-directed | Added governed branch/worktree registration, cleanup lifecycle, preservation controls, receipts, risks, and phase gates |

## Review and Approval

| Role | Name | Decision / Status | Date | Notes |
|---|---|---|---|---|
| Author | OpenAI ChatGPT, operator-directed | Amended | 2026-07-21 | Added repository-hygiene governance at operator direction |
| Reviewer | Pending independent reviewer | Pending |  | Must review exact amended PR head |
| Approver | Bobby Fetting | Pending |  | Merge and Phase B authorization remain separate |

## Final Disposition

**Disposition:** `PROPOSED — AMENDED IN PR #318; INDEPENDENT REVIEW REQUIRED`

**Next Gate:** Independent Phase A pull-request review against the exact amended
head SHA.

**Residual Risks / Open Items:**

- Phase B through Phase E remain unimplemented.
- No existing branch or worktree has yet been inventoried under the new policy.
- GitHub branch rules, cleanup tooling, registry, and required review checks
  remain Phase C work.

> End of governed artifact.
