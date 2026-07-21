---
title: "Branch and Worktree Lifecycle Policy"
artifact_id: "POL-GIT-HYGIENE-001"
classification: "Repository Governance"
artifact_type: "Policy"
version: "0.1"
status: "Proposed"
date_created: "2026-07-21"
date_updated: "2026-07-21"
owner: "Bobby Fetting"
repository: "RMF112018/hb-personal-assistant"
related_artifacts:
  - "ADR-019"
  - "GitHub issue #317"
  - "docs/implementation-plans/github-first-control-plane-migration.md"
tags:
  - aeos
  - git
  - worktree
  - branch
  - hygiene
  - lifecycle
---

# Branch and Worktree Lifecycle Policy

## 1. Purpose

This policy prevents abandoned branches, stale worktrees, hidden unique commits,
and ambiguous local repository state from becoming part of the normal
multi-agent delivery process.

Branch and worktree cleanup is a governed closeout activity. A pull request
merge is not, by itself, completion of the associated work item.

## 2. Scope

This policy applies to:

- the canonical local checkout;
- every linked Git worktree for this repository;
- every local branch;
- every remote branch under the repository's control;
- Claude Code, Codex, Grok, Composer, ChatGPT-operated tools, local scripts, and
  any future approved implementation harness;
- human operators when executing an AEOS-governed work item.

It does not authorize deletion. It defines the evidence and authorization
required before deletion or retention.

## 3. Authority and Responsibilities

### 3.1 Operator

The operator retains authority to:

- approve creation of exceptional long-lived branches or worktrees;
- approve deletion of remote branches when deletion is not already authorized
  by an accepted repository policy or explicit work-item authorization;
- accept residual risk;
- approve forceful recovery actions;
- decide retention when evidence is incomplete or conflicting.

### 3.2 Implementing Agent

An implementing agent must:

- register the branch and worktree before substantive editing;
- operate only in the registered worktree and branch;
- report dirty state and unexpected repository identities immediately;
- preserve unique work before proposing cleanup;
- complete the post-merge cleanup checkpoint or explicitly record why cleanup
  is blocked;
- never classify its own uncertain work as safely disposable.

### 3.3 Independent Reviewer

An independent reviewer verifies cleanup evidence when required by the active
work item, finding, or gate. The reviewer must not perform destructive cleanup
as part of the independent review context.

## 4. Canonical Checkout

One checkout must be designated as the canonical checkout. Its role is to:

- track the canonical default branch;
- provide a stable location for repository-wide inspection and maintenance;
- avoid feature implementation unless explicitly authorized;
- remain free of unrelated uncommitted changes.

The canonical checkout must not be removed by an agent.

## 5. Required Registration

Before substantive work, each non-canonical worktree must have a durable
registration containing, at minimum:

```yaml
worktree_id: <stable-id>
repository: RMF112018/hb-personal-assistant
absolute_path: <path>
branch: <branch>
base_branch: main
base_sha: <sha>
owner_or_agent: <identity>
goal_id: <goal-id-or-null>
work_item_id: <work-item-id>
issue: <issue-number-or-null>
pull_request: <pr-number-or-null>
created_at: <timestamp>
expected_disposition: remove-after-merge | retain-by-decision
status: ACTIVE
```

Registration may initially be recorded manually. Phase C must introduce a
canonical machine-readable registry and validator.

Unregistered implementation work is a governance finding. Discovery of an
unregistered worktree does not authorize its deletion.

## 6. Lifecycle States

Every non-canonical worktree and associated branch must resolve to exactly one
of the following lifecycle states:

| State | Meaning |
|---|---|
| `REGISTERED` | Created and associated with a governed work item; no substantive work has begun |
| `ACTIVE` | Authorized implementation or corrective work is in progress |
| `REVIEW_PENDING` | Work is submitted for review; branch and worktree must be preserved |
| `CHANGES_REQUESTED` | Review requires corrective work; branch and worktree remain active |
| `MERGED_PENDING_CLEANUP` | Pull request is merged, but local and remote disposition is incomplete |
| `CLEANUP_BLOCKED` | Cleanup cannot safely proceed; reason and evidence are recorded |
| `RETAINED_BY_DECISION` | Operator or accepted policy requires continued retention |
| `CLEANUP_VERIFIED` | Authorized cleanup completed and evidence recorded |
| `CLOSED` | Work item, branch, and worktree dispositions are fully reconciled |

Diagnostic classifications may supplement the lifecycle state:

- `DIRTY_REQUIRES_PRESERVATION`
- `UNMERGED_UNIQUE_COMMITS`
- `PATCH_EQUIVALENT_TO_MAIN`
- `DETACHED_HEAD`
- `ORPHANED_REGISTRATION`
- `PROCESS_IN_USE`
- `REMOTE_BRANCH_PRESENT`
- `LOCAL_BRANCH_PRESENT`
- `WORKTREE_METADATA_STALE`

## 7. Creation Rules

Agents must not create a branch or worktree unless:

1. the work item is identified;
2. the base branch and base SHA are recorded;
3. the branch name is unique and scoped to the work item;
4. the worktree path is deterministic or recorded immediately;
5. the expected cleanup disposition is declared;
6. existing worktrees and branches are inspected for conflicts or reusable
   active work;
7. creation is within the active authorization.

A new worktree must not be created merely because the current checkout is dirty
without first identifying and reporting the owner and purpose of the existing
changes.

## 8. Completion Rule

A governed work item is not operationally complete when its pull request is
merged.

It is complete only when:

1. post-merge validation has passed or is explicitly not required;
2. the merge commit or equivalent integration identity is recorded;
3. the worktree is clean, or every remaining change is preserved and assigned;
4. the branch tip is proven integrated, intentionally retained, or preserved;
5. local branch disposition is verified;
6. worktree disposition is verified;
7. remote branch disposition is verified or explicitly deferred;
8. cleanup evidence and any blockers are recorded;
9. no unresolved repository-hygiene finding remains for the work item.

## 9. Preconditions for Worktree Removal

Before removing a worktree, the cleanup executor must verify and record:

- worktree absolute path;
- associated branch and work item;
- `git status --short --branch` result;
- current branch tip SHA;
- base/default branch and current `origin/main` SHA;
- pull-request state and merge identity when applicable;
- whether the branch tip is reachable from `origin/main`;
- whether `git cherry` or an equivalent patch-equivalence check identifies
  unique changes;
- whether untracked, ignored-but-material, staged, or unstaged files exist;
- whether a running process has the path as its working directory or is using
  repository services from that worktree;
- whether linked evidence or generated artifacts still depend on the path;
- the authorization permitting cleanup.

If any result is uncertain, cleanup fails closed to `CLEANUP_BLOCKED`.

## 10. Permitted Cleanup Sequence

The normal cleanup sequence is:

1. fetch and prune remote references without deleting local work;
2. verify the exact pull request and merge result;
3. verify the worktree is clean;
4. prove branch integration or patch equivalence;
5. stop or relocate authorized processes using the worktree;
6. remove the linked worktree without force;
7. prune stale worktree metadata;
8. delete the local branch with `git branch -d`;
9. delete the remote branch only when separately authorized or covered by an
   accepted automatic-delete policy;
10. run a final inventory;
11. write the cleanup receipt.

Failure at any step stops the sequence. Later steps must not be forced merely to
obtain a clean inventory.

## 11. Prohibited Routine Actions

Agents must not use the following as routine hygiene mechanisms:

- `git reset --hard`;
- `git clean -fd`, `git clean -fdx`, or equivalent broad deletion;
- `git worktree remove --force`;
- `git branch -D` after `git branch -d` refuses;
- force-push to make a branch appear integrated;
- deletion of a dirty worktree;
- deletion of a branch containing unproven unique commits;
- deletion based only on branch age;
- deletion based only on a merged pull-request label or summary claim;
- manual removal of worktree directories before Git worktree reconciliation;
- silent abandonment of a worktree after merge.

A forceful recovery action requires explicit operator authorization, a
preservation plan, and a recovery receipt.

## 12. Remote Branch Policy

Local worktree removal, local branch deletion, and remote branch deletion are
three separate actions.

Remote deletion requires one of:

- explicit operator authorization for the work item;
- an accepted repository rule enabling automatic head-branch deletion after
  merge, with protected and retained branches excluded;
- a later accepted hygiene policy that defines deterministic eligibility and
  recovery evidence.

Remote branches associated with open pull requests, unique commits, releases,
hotfix retention, or unresolved findings must be preserved.

## 13. Cleanup Receipt

Every completed or blocked cleanup must produce a durable receipt containing:

```yaml
receipt_id: <stable-id>
worktree_id: <stable-id>
goal_id: <goal-id-or-null>
work_item_id: <work-item-id>
issue: <issue-number-or-null>
pull_request: <pr-number-or-null>
worktree_path: <path>
branch: <branch>
branch_tip_before: <sha>
origin_main_at_check: <sha>
merge_commit: <sha-or-null>
integration_proof: reachable | patch-equivalent | retained | blocked
worktree_dirty_before: true | false
process_check: clear | blocked | not-available
local_branch_disposition: deleted | retained | blocked
remote_branch_disposition: deleted | retained | deferred | blocked
worktree_disposition: removed | retained | blocked
commands_or_checks: []
completed_at: <timestamp>
executor: <identity>
authorization_id: <id>
findings: []
```

Receipts must not contain credentials, tokens, or sensitive process data.

## 14. Inventory and Reconciliation

Until Phase C automation exists, agents must include the following in material
closeout reports:

- `git worktree list --porcelain` summary;
- local branch inventory relevant to the work item;
- remote branch disposition relevant to the work item;
- dirty worktree findings;
- retained or blocked items and reasons.

Phase C must implement deterministic inventory and reconciliation capable of:

- linking branches and worktrees to goals, work items, issues, and pull requests;
- detecting orphaned, dirty, merged, blocked, and retained state;
- producing proposed actions without destructive defaults;
- executing only explicitly authorized actions;
- producing machine-readable receipts.

## 15. Staleness and Escalation

A worktree or branch is stale when it has exceeded the repository's configured
activity threshold and lacks an active review, authorization, or retention
decision. Age alone is not deletion proof.

Stale items must be classified and surfaced to the operator. They remain
preserved until integration, retention, or cleanup eligibility is proven.

## 16. Phase Mapping

- **Phase A:** adopt this policy and the completion invariant.
- **Phase B:** exercise the full branch/worktree lifecycle on the pilot goal and
  produce at least one cleanup receipt.
- **Phase C:** implement the registry, semantic validator, reconciliation tool,
  and appropriate GitHub branch-deletion/ruleset controls.
- **Phase D:** publish hygiene status in the generated control-plane dashboard
  and eliminate redundant manual inventories.
- **Phase E:** verify every approved harness follows the same creation,
  preservation, cleanup, and receipt contract.

## 17. Acceptance Criteria

| ID | Criterion |
|---|---|
| `AC-GIT-HYGIENE-001` | Every new non-canonical worktree is registered to a work item before substantive editing |
| `AC-GIT-HYGIENE-002` | Merge transitions work to `MERGED_PENDING_CLEANUP`, not directly to `CLOSED` |
| `AC-GIT-HYGIENE-003` | Dirty or uniquely committed work is preserved and blocks automatic deletion |
| `AC-GIT-HYGIENE-004` | Normal cleanup uses non-force worktree removal and `git branch -d` |
| `AC-GIT-HYGIENE-005` | Remote branch deletion is independently authorized or policy-controlled |
| `AC-GIT-HYGIENE-006` | Cleanup produces a durable machine-readable receipt |
| `AC-GIT-HYGIENE-007` | Phase C validation detects orphaned, blocked, and unresolved hygiene state |
| `AC-GIT-HYGIENE-008` | All approved harnesses pass the lifecycle conformance scenario |

## 18. Current Disposition

**Disposition:** `PROPOSED — PART OF PHASE A PR #318`

**Next Gate:** Independent review of this policy together with ADR-019 and the
Phase A migration package against the exact pull-request head SHA.
