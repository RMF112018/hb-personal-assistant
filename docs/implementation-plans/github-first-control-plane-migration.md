---
title: "GitHub-First Control-Plane Migration Plan"
artifact_id: "PLAN-GITHUB-FIRST-CONTROL-PLANE-001"
classification: "Plans"
artifact_type: "Implementation and Migration Plan"
version: "1.0"
status: "Phase A Accepted — Phases B–E Not Authorized"
date_created: "2026-07-21"
date_updated: "2026-07-21"
owner: "Bobby Fetting"
repository: "RMF112018/hb-personal-assistant"
tracking_issue: "#317"
related_adr: "ADR-019"
related_policy: "POL-GIT-HYGIENE-001"
phase_a_acceptance:
  pull_request: 318
  reviewed_head_sha: "3abddb08751c702fdd73e54e3a0b9e9543099059"
  review_disposition: "APPROVE"
  merge_commit: "8b44cbd216d531a1894b4257355469edf922029f"
phase_b_authorized: false
---

# GitHub-First Control-Plane Migration Plan

## Objective

Move active multi-agent engineering execution to a GitHub-first hybrid while
preserving AEOS governance, operator authorization, independent review, durable
evidence, Workspace history, and safe branch/worktree lifecycle management.

## Target operating model

| Information | Canonical location |
|---|---|
| Source and repository governance | Git repository |
| Goals and work items | GitHub issues and repository goal records |
| Active branch, base/head SHA, PR, checks, merge | GitHub |
| Branch/worktree identity and lifecycle | Repository records plus authenticated Git evidence |
| Independent review | Exact-head GitHub review/check/comment record |
| Cleanup/retention/blocker receipts | Repository evidence linked to work item |
| Runtime behavior | Deployed runtime and runtime evidence |
| Publication and external handoff | Google Drive |
| Final authorization and risk acceptance | Operator |

## Global constraints

- Preserve Drive history and stable IDs.
- Do not treat publication failure as engineering-state failure.
- Do not treat merge as deployment, production authority, or closeout.
- Maintain implementer/reviewer separation and exact-SHA review.
- Preserve dirty, untracked, unique, inaccessible, locked, and process-dependent
  work.
- Treat worktree removal, local branch deletion, remote deletion, metadata
  pruning, and remote-reference pruning as distinct actions.
- Inventory and preserve before prune or deletion.
- Do not use force-based cleanup as routine hygiene.
- Reuse the permanent-identity goal for the Phase B pilot only after separate
  operator authorization.

## Governing lifecycle

The accepted policy is:

```text
docs/governance/branch-worktree-lifecycle-policy.md
```

Normal lifecycle:

```text
REGISTERED → ACTIVE → REVIEW_PENDING
REVIEW_PENDING → CHANGES_REQUESTED | MERGED_PENDING_CLEANUP
CHANGES_REQUESTED → ACTIVE | REVIEW_PENDING
MERGED_PENDING_CLEANUP → CLEANUP_VERIFIED | RETAINED_BY_DECISION | CLEANUP_BLOCKED
CLEANUP_VERIFIED → CLOSED
```

Current branch tips and exact review candidates are authenticated external Git
identities. Repository registrations preserve immutable registration/transition
facts and do not claim to contain their own current commit SHA.

## Phase A — Authority decision and lifecycle contract

### Status

`ACCEPTED AND MERGED`

### Deliverables

- ADR-019;
- POL-GIT-HYGIENE-001;
- Phase A repository-hygiene evidence;
- updated root agent guidance;
- GitHub issue #317 and PR #318;
- Drive publication/reference notice and operating-control updates.

### Completed gate evidence

- PR #318 base: `e30c63846f36f7fa59b7784c2f345d8483a566f9`.
- Independently reviewed head: `3abddb08751c702fdd73e54e3a0b9e9543099059`.
- Review disposition: `APPROVE`.
- Operator exact-head squash merge: main commit
  `8b44cbd216d531a1894b4257355469edf922029f` on 2026-07-21.
- Phase A changed governance/documentation/evidence only.
- No Phase B activation, existing-entity cleanup, deployment, migration,
  production activation, or risk acceptance was authorized.

### Phase A completion meaning

Phase A accepted the authority model and lifecycle policy. It did not prove the
full pilot lifecycle, reconcile every existing branch/worktree, implement
registry automation, or authorize later phases.

## Phase B — Pilot one goal and full lifecycle

### Status

`NOT AUTHORIZED`

### Pilot candidate

`GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001`

### Purpose

Prove the target model and preservation-first lifecycle against one real governed
workstream before broader migration.

### Required actions

1. Issue an exact operator authorization for Phase B and the first bounded work
   item.
2. Map the goal/work items to repository and GitHub identities while preserving
   Drive history and hashes.
3. Create schema-v2 branch registrations and worktree registrations.
4. Bind authorization, branch/worktree, base/head SHAs, PR, review, checkpoint,
   and evidence to exact identities.
5. Record each lifecycle transition and authority.
6. Obtain independent exact-head review.
7. After separately authorized merge, transition to
   `MERGED_PENDING_CLEANUP`.
8. Perform or explicitly waive post-merge validation under exact authority.
9. Inventory all relevant worktrees, refs, tags, refspecs, remote tips, dirty
   state, locks, storage, process use, and evidence dependencies before cleanup.
10. Fetch without pruning and preserve unique/uncertain identities.
11. Prove integration or patch equivalence.
12. Preview and review worktree metadata pruning; block unrelated effects.
13. Remove only exact eligible worktrees without force.
14. Delete eligible local branches with `git branch -d`.
15. Resolve remote disposition separately.
16. Preview and execute remote-reference pruning only under exact authorization.
17. Produce cleanup, retention, or blocker receipts and final inventory.
18. Publish a read-only Drive summary pointing to canonical identities.

### Branch registration contract

Use schema version 2 from POL-GIT-HYGIENE-001. The repository record contains
`registration_tip_sha`, not `branch_tip_sha`; current tip and exact review
candidate are resolved from authenticated GitHub/local Git and external review
records.

### Completion gate

- one real goal completes or explicitly blocks the full lifecycle;
- current state is resolvable without reading full Drive history;
- review is exact-head bound;
- branch-only, remote-only, detached, retained, and blocked cases are
  deterministic;
- no prune occurs before inventory and preservation;
- no force-based cleanup occurs;
- at least one machine-readable cleanup, retention, or blocker receipt exists;
- no historical or uncertain work is lost.

## Phase C — Enforcement and reconciliation

### Status

`NOT AUTHORIZED`

### Required actions

- implement canonical validation of goal state, branch/worktree registrations,
  transitions, authorizations, PR/review identity, and cleanup receipts;
- invalidate stale reviews when head changes;
- reconcile GitHub, goal, branch, and worktree lifecycle state;
- implement deterministic inventory and dry-run cleanup proposals;
- require preservation/integration proof before cleanup;
- preview metadata and remote-reference pruning and require separate authority for
  unrelated effects;
- preserve failed/blocked attempts;
- add selected branch rules and required checks;
- decide automatic head-branch deletion policy.

### Completion gate

Semantic validation fails closed, changed heads invalidate current review,
active entities resolve to registrations or findings, unsafe states block
cleanup, all prune effects are previewed, and eligible cleanup produces valid
receipts.

## Phase D — Consolidation and dashboard

### Status

`NOT AUTHORIZED`

Generate concise Drive publication from canonical repository/GitHub state,
retire redundant manual execution-state ledgers, preserve historical artifacts,
and expose active, retained, blocked, detached, inaccessible, and stale entities
without treating age as deletion proof.

## Phase E — Cross-harness lifecycle validation

### Status

`NOT AUTHORIZED`

Validate Claude Code, Codex, Grok, Composer, ChatGPT, and future harnesses against
the same canonical state, registration, transition, review, preservation,
cleanup, and receipt contracts. Adapters may fail closed but may not reinterpret
or weaken canonical governance.

## Validation strategy for every phase

Capture base/head SHAs, files/settings changed, exact commands/results, scope and
exclusions, Drive IDs touched, entity identities/dispositions, pre/post
inventories, prune previews and authority, preservation artifacts, receipts,
deviations, independent review, and operator authorization for the next phase.

## Recovery

Prefer forward correction while preserving events, reviews, receipts, and
uncertain work. Rollback or cleanup is separately authorized and must not erase
historical evidence.

## Current disposition

- **Phase A:** `ACCEPTED AND MERGED`.
- **Phase B:** `NOT AUTHORIZED`.
- **Phase C:** `NOT AUTHORIZED`.
- **Phase D:** `NOT AUTHORIZED`.
- **Phase E:** `NOT AUTHORIZED`.

The next phase may begin only through a separate exact operator authorization.
