---
title: "Branch and Worktree Lifecycle Policy"
artifact_id: "POL-GIT-HYGIENE-001"
classification: "Repository Governance"
artifact_type: "Policy"
version: "1.0"
status: "Accepted — Phase A"
date_created: "2026-07-21"
date_updated: "2026-07-21"
owner: "Bobby Fetting"
repository: "RMF112018/hb-personal-assistant"
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
related_artifacts:
  - "ADR-019"
  - "GitHub issue #317"
  - "docs/implementation-plans/github-first-control-plane-migration.md"
  - "docs/evidence/github-first-control-plane-phase-a/phase-a-repository-hygiene-evidence.md"
tags: [aeos, git, worktree, branch, hygiene, lifecycle]
---

# Branch and Worktree Lifecycle Policy

## 1. Purpose and scope

This policy prevents abandoned branches, stale worktrees, hidden unique commits,
and ambiguous local state from becoming normal multi-agent delivery behavior. It
applies to the canonical checkout, linked worktrees, local and remote branches,
remote-tracking references, relevant tags and metadata, all approved agent
harnesses, and human operators executing AEOS-governed work.

It does not authorize deletion. It defines evidence, lifecycle state, and
authority required before creation, cleanup, retention, pruning, or deletion.

## 2. Authority

The operator retains authority for exceptional long-lived entities, remote
branch deletion unless already covered by accepted policy or exact
authorization, broad pruning, forceful recovery, retention under uncertainty,
risk acceptance, merge, deployment, and production activation.

Implementing agents register entities before substantive work, operate only in
the registered branch/worktree, preserve uncertain work, record transitions and
authority, and stop at the required checkpoint. Independent reviewers verify
bounded evidence and do not perform destructive cleanup in the review context.

## 3. Canonical checkout

One checkout is designated canonical. It tracks the default branch, supports
repository-wide inspection, avoids feature implementation unless explicitly
authorized, remains free of unrelated changes, and is never removed by an agent.

## 4. Identity model

Branches and worktrees are distinct governed entities.

- A branch has a stable `branch_id` even with no local branch or worktree.
- A worktree has a stable `worktree_id` and references a branch or detached SHA.
- One work item may have multiple entities, each with distinct identity and an
  explicit relationship.
- Local, remote, and tracking representations are not collapsed into one field.
- Orphaned or unregistered entities create findings; discovery does not authorize
  deletion.

### 4.1 Non-self-referential branch identity

An in-repository file cannot authoritatively contain the SHA of the commit that
contains that file. Therefore:

- `registration_tip_sha` records the immutable tip observed before the
  registration record was first committed;
- a transition may record `evidence_parent_sha`, the immutable parent on which
  the transition evidence was prepared;
- the current branch tip is resolved from authenticated GitHub or local Git at
  inspection time and is not stored as a self-referential `branch_tip_sha`;
- the exact review candidate and reviewed SHA are external GitHub PR/review
  identities and must be recorded in the PR conversation, review, required check,
  or other immutable external receipt;
- repository records identify the authority and location for current-tip and
  review-candidate resolution rather than copying a value that becomes stale on
  commit.

The fields `branch_tip_sha` and `candidate_head_sha` are prohibited in schema
version 2 branch-registration files.

### 4.2 Branch registration schema version 2

```yaml
schema_version: 2
branch_id: <stable-id>
repository: RMF112018/hb-personal-assistant
local_branch: <name-or-null>
remote_name: origin | <other-or-null>
remote_branch: <name-or-null>
remote_tracking_ref: <ref-or-null>
registration_tip_sha: <immutable-sha-observed-before-registration-commit>
current_tip_authority: authenticated_github | local_git
current_tip_recorded_in_repository: false
review_candidate_binding: external_exact_sha_review
base_branch: main
base_sha: <sha>
owner_or_agent: <identity>
goal_id: <goal-id-or-null>
work_item_id: <work-item-id-or-null>
issue: <issue-number-or-null>
pull_request: <pr-number-or-null>
created_at: <timestamp-or-unknown>
registered_at: <timestamp>
expected_disposition: remove-after-merge | retain-by-decision | investigate
lifecycle_state: REGISTERED
retention_reason: <reason-or-null>
next_review_at: <timestamp-or-null>
transitions: []
```

A remote-only branch sets `local_branch: null`. An orphaned branch sets unresolved
relationships to `null` and remains `CLEANUP_BLOCKED` until reconciled.

### 4.3 Worktree registration

```yaml
schema_version: 1
worktree_id: <stable-id>
repository: RMF112018/hb-personal-assistant
absolute_path: <path>
branch_id: <stable-branch-id-or-null>
detached_head_sha: <sha-or-null>
owner_or_agent: <identity>
goal_id: <goal-id-or-null>
work_item_id: <work-item-id-or-null>
issue: <issue-number-or-null>
pull_request: <pr-number-or-null>
created_at: <timestamp-or-unknown>
registered_at: <timestamp>
expected_disposition: remove-after-merge | retain-by-decision | investigate
lifecycle_state: REGISTERED
locked: true | false | unknown
storage_class: local | portable | network | cloud-synced | unknown
retention_reason: <reason-or-null>
next_review_at: <timestamp-or-null>
```

A detached worktree sets `branch_id: null` and records `detached_head_sha`.
Unknown or inaccessible paths fail closed to preservation.

## 5. Lifecycle states

| State | Meaning |
|---|---|
| `REGISTERED` | Associated with governed work; substantive work not begun |
| `ACTIVE` | Authorized implementation or corrective work in progress |
| `REVIEW_PENDING` | Submitted for review; entities preserved |
| `CHANGES_REQUESTED` | Review requires correction; entities preserved |
| `MERGED_PENDING_CLEANUP` | PR merged; validation and dispositions incomplete |
| `CLEANUP_BLOCKED` | Evidence, access, authority, or safety blocks cleanup |
| `RETAINED_BY_DECISION` | Operator or accepted policy requires retention |
| `CLEANUP_VERIFIED` | Authorized cleanup completed and evidenced |
| `CLOSED` | Work item and all entity dispositions reconciled |

Normal transitions:

```text
REGISTERED → ACTIVE
ACTIVE → REVIEW_PENDING
REVIEW_PENDING → CHANGES_REQUESTED | MERGED_PENDING_CLEANUP
CHANGES_REQUESTED → ACTIVE | REVIEW_PENDING
MERGED_PENDING_CLEANUP → CLEANUP_VERIFIED | RETAINED_BY_DECISION | CLEANUP_BLOCKED
CLEANUP_BLOCKED → MERGED_PENDING_CLEANUP | RETAINED_BY_DECISION
RETAINED_BY_DECISION → MERGED_PENDING_CLEANUP | CLOSED
CLEANUP_VERIFIED → CLOSED
```

Transitions outside this graph require explicit operator authorization.

Each transition records stable ID, entity type and ID, from/to state, timestamp,
actor, authorization, evidence, reason, and—when prepared in the same branch—an
optional immutable `evidence_parent_sha`. Current GitHub tip and exact reviewed
SHA remain externally resolved identities.

Diagnostic classifications may supplement but not replace lifecycle state,
including dirty preservation, unique commits, patch equivalence, detached head,
orphan registration, process use, remote/local presence, stale metadata,
unavailable path, and locked worktree.

## 6. Creation rules

Do not create a branch or worktree unless the work item, base branch/SHA, unique
name, registrations, expected disposition, conflict inspection, and active
authorization are established. A new worktree is not a workaround for unrelated
dirty state without first preserving and assigning that state.

## 7. Completion rule

PR merge is not operational completion. Completion requires post-merge
validation or exact not-required authorization, integration identity, preserved
remaining material, branch integration/retention proof, local branch and
worktree disposition, remote disposition or explicit deferral, cleanup evidence,
and no unresolved hygiene finding.

## 8. Cleanup preconditions

Before worktree removal, branch deletion, or reference/metadata pruning, record:

- exact entity and work-item identities;
- worktree path and `git status --short --branch` where accessible;
- branch/detached tips, local refs, tracking refs, tags, fetch refspecs, and
  relevant remote tips;
- current default-branch SHA, PR state, reviewed head, and merge identity;
- reachability and patch-equivalence analysis;
- staged, unstaged, untracked, and material ignored files;
- process use and evidence dependencies;
- lock and storage state;
- exact authorization for each action.

Any uncertainty yields `CLEANUP_BLOCKED`.

## 9. Preservation-first sequence

1. Capture the complete pre-cleanup inventory before fetch, prune, repair, or
   deletion.
2. Fetch without pruning.
3. Preserve unique or uncertain identities through authorized refs, tags,
   bundles, patches, or equivalent recovery evidence.
4. Verify exact PR and integration identity.
5. Verify post-merge validation, dirty state, evidence dependencies, locks,
   storage, and process use.
6. Remove only the exact eligible linked worktree without force.
7. Preview worktree pruning with `git worktree prune --dry-run --verbose` or an
   equivalent read-only command and review every proposed removal.
8. Prefer target-specific repair. Unrelated proposed metadata effects require
   separate authorization and block broad pruning.
9. Delete eligible local branches only with `git branch -d`.
10. Resolve remote branch disposition separately.
11. Preview remote-tracking pruning and record former SHAs before authorized
    execution.
12. Capture final inventory and a cleanup, retention, or blocker receipt.

Routine hygiene must not use `git reset --hard`, broad `git clean`, forced
worktree removal, `git branch -D`, prune-before-proof, or history rewrite.

## 10. Retention and blocked state

Retention records the reason, authority, owner, review condition, and
`next_review_at`. Age is never deletion proof. Inaccessible, locked, network,
cloud-synced, process-dependent, dirty, unique, or uncertain entities remain
preserved until evidence and authority are sufficient.

## 11. Required receipt

A closeout receipt records repository, goal/work item, PR, reviewed head, merge
identity, post-merge validation, pre/post inventory, entity IDs, preservation
artifacts, exact commands and exit codes, worktree/local/remote dispositions,
prune previews and approvals, retained or blocked reasons, review conditions,
actor, authorization, timestamps, residual findings, and final lifecycle state.
Failed and blocked attempts remain part of the record.

## 12. Acceptance and phase boundary

This policy was independently reviewed at PR #318 head
`3abddb08751c702fdd73e54e3a0b9e9543099059` with disposition `APPROVE` and was
operator-accepted through the exact-head squash merge to
`8b44cbd216d531a1894b4257355469edf922029f` on 2026-07-21.

Acceptance adopts the Phase A policy. It does not authorize Phase B, cleanup of
existing entities, deployment, migration, production activation, or risk
acceptance.
