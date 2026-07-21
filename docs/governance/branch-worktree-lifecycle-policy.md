---
title: "Branch and Worktree Lifecycle Policy"
artifact_id: "POL-GIT-HYGIENE-001"
classification: "Repository Governance"
artifact_type: "Policy"
version: "0.2"
status: "Proposed"
date_created: "2026-07-21"
date_updated: "2026-07-21"
owner: "Bobby Fetting"
repository: "RMF112018/hb-personal-assistant"
related_artifacts:
  - "ADR-019"
  - "GitHub issue #317"
  - "docs/implementation-plans/github-first-control-plane-migration.md"
  - "docs/evidence/github-first-control-plane-phase-a/phase-a-repository-hygiene-evidence.md"
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

Branch and worktree reconciliation is a governed closeout activity. A pull
request merge is not, by itself, completion of the associated work item.

## 2. Scope

This policy applies to:

- the canonical local checkout;
- every linked Git worktree for this repository;
- every local branch;
- every remote branch under the repository's control;
- remote-tracking references and worktree administrative metadata when a cleanup
  action could remove or rewrite them;
- Claude Code, Codex, Grok, Composer, ChatGPT-operated tools, local scripts, and
  any future approved implementation harness;
- human operators when executing an AEOS-governed work item.

It does not authorize deletion. It defines the evidence, state, and authority
required before cleanup, retention, pruning, or deletion.

## 3. Authority and Responsibilities

### 3.1 Operator

The operator retains authority to:

- approve creation of exceptional long-lived branches or worktrees;
- approve deletion of remote branches when deletion is not already authorized
  by an accepted repository policy or exact work-item authorization;
- approve pruning that can affect references or worktree metadata outside the
  exact item being closed;
- accept residual risk;
- approve forceful recovery actions;
- decide retention when evidence is incomplete or conflicting.

### 3.2 Implementing Agent

An implementing agent must:

- register branch and worktree identities before substantive editing;
- operate only in the registered worktree and branch;
- record every lifecycle transition and its authority;
- report dirty state and unexpected repository identities immediately;
- preserve unique or uncertain work before proposing cleanup;
- complete the post-merge cleanup checkpoint or explicitly record why cleanup
  is blocked or retention is required;
- never classify its own uncertain work as safely disposable.

### 3.3 Independent Reviewer

An independent reviewer verifies cleanup evidence when required by the active
work item, finding, or gate. The reviewer must not perform destructive cleanup,
reference pruning, or metadata pruning as part of the independent review
context.

## 4. Canonical Checkout

One checkout must be designated as the canonical checkout. Its role is to:

- track the canonical default branch;
- provide a stable location for repository-wide inspection and maintenance;
- avoid feature implementation unless explicitly authorized;
- remain free of unrelated uncommitted changes.

The canonical checkout must not be removed by an agent.

## 5. Canonical Identity Model

Branches and worktrees are separate governed entities.

- A branch has a stable `branch_id` even when it has no linked worktree.
- A worktree has a stable `worktree_id` and may link to one branch or to a
  detached-head commit.
- A work item may legitimately have multiple branch and worktree records. Each
  record must have a distinct stable identity and an explicit relationship.
- Local, remote, and remote-tracking representations must not be collapsed into
  a single ambiguous `branch` field.
- Discovery of an orphaned or unregistered entity creates a finding; it does not
  authorize deletion.

### 5.1 Branch Registration

Before substantive work, each non-canonical branch must have a durable record
containing, at minimum:

```yaml
schema_version: 1
branch_id: <stable-id>
repository: RMF112018/hb-personal-assistant
local_branch: <name-or-null>
remote_name: origin | <other-or-null>
remote_branch: <name-or-null>
remote_tracking_ref: <ref-or-null>
branch_tip_sha: <sha>
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
```

This model supports:

- a local branch with no worktree;
- a remote-only branch by setting `local_branch: null`;
- an orphaned branch by setting the unresolved relationship fields to `null` and
  lifecycle state to `CLEANUP_BLOCKED` until reconciled;
- a retained branch with a reason and next review date.

### 5.2 Worktree Registration

Each non-canonical worktree must have a separate durable record:

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

A detached-head worktree must set `branch_id: null` and record
`detached_head_sha`. A worktree with an unknown or inaccessible path must remain
preserved and classified as blocked until reconciled.

Registration may initially be recorded manually. Phase C must introduce a
canonical machine-readable registry and validator.

## 6. Lifecycle States and Transitions

Every branch and worktree record must resolve to exactly one lifecycle state:

| State | Meaning |
|---|---|
| `REGISTERED` | Associated with a governed work item; no substantive work has begun |
| `ACTIVE` | Authorized implementation or corrective work is in progress |
| `REVIEW_PENDING` | Work is submitted for review; branch and worktree must be preserved |
| `CHANGES_REQUESTED` | Review requires corrective work; branch and worktree remain active |
| `MERGED_PENDING_CLEANUP` | Pull request is merged, but post-merge validation and dispositions are incomplete |
| `CLEANUP_BLOCKED` | Cleanup cannot safely proceed; reason, evidence, and review condition are recorded |
| `RETAINED_BY_DECISION` | Operator or accepted policy requires continued retention with review conditions |
| `CLEANUP_VERIFIED` | Authorized cleanup completed and evidence recorded |
| `CLOSED` | Work item and all linked entity dispositions are fully reconciled |

Allowed normal transitions are:

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

Each transition must record:

```yaml
transition_id: <stable-id>
entity_type: branch | worktree
entity_id: <branch-id-or-worktree-id>
from_state: <state>
to_state: <state>
occurred_at: <timestamp>
actor: <identity>
authorization_id: <id-or-policy-reference>
evidence: <path-or-url-or-null>
reason: <reason>
```

Transitions outside the normal graph require explicit operator authorization and
must be preserved as exceptional transitions.

Diagnostic classifications may supplement, but never replace, lifecycle state:

- `DIRTY_REQUIRES_PRESERVATION`
- `UNMERGED_UNIQUE_COMMITS`
- `PATCH_EQUIVALENT_TO_MAIN`
- `DETACHED_HEAD`
- `ORPHANED_REGISTRATION`
- `PROCESS_IN_USE`
- `REMOTE_BRANCH_PRESENT`
- `LOCAL_BRANCH_PRESENT`
- `WORKTREE_METADATA_STALE`
- `PATH_TEMPORARILY_UNAVAILABLE`
- `LOCKED_WORKTREE`

## 7. Creation Rules

Agents must not create a branch or worktree unless:

1. the work item is identified;
2. the base branch and base SHA are recorded;
3. the branch name is unique and scoped to the work item;
4. branch and worktree registrations are created immediately;
5. the expected cleanup disposition is declared;
6. existing worktrees and branches are inspected for conflicts or reusable active
   work;
7. creation is within the active authorization.

A new worktree must not be created merely because the current checkout is dirty
without first identifying and reporting the owner and purpose of the existing
changes.

## 8. Completion Rule

A governed work item is not operationally complete when its pull request is
merged.

It is complete only when:

1. post-merge validation has passed or an exact operator authorization records
   that it is not required;
2. the merge commit or equivalent integration identity is recorded;
3. the worktree is clean, or every remaining change is preserved and assigned;
4. the branch tip is proven integrated, intentionally retained, or preserved;
5. local branch disposition is verified;
6. worktree disposition is verified;
7. remote branch disposition is verified or explicitly deferred with a reason
   and review condition;
8. cleanup evidence and any blockers are recorded;
9. no unresolved repository-hygiene finding remains for the work item.

## 9. Preconditions for Cleanup or Removal

Before removing a worktree, deleting a branch, or pruning references or metadata,
the cleanup executor must verify and record:

- exact target entity IDs and work item;
- worktree absolute path when applicable;
- `git status --short --branch` result for each accessible target worktree;
- current branch and detached-head tip SHAs;
- current local refs, remote-tracking refs, tags, configured fetch refspecs, and
  remote branch tips relevant to the target;
- base/default branch and current `origin/main` SHA;
- pull-request state and merge identity when applicable;
- whether each branch tip is reachable from `origin/main`;
- whether `git cherry` or equivalent patch-equivalence analysis identifies
  unique changes;
- whether untracked, ignored-but-material, staged, or unstaged files exist;
- whether a running process has the path as its working directory or is using
  repository services from that worktree;
- whether linked evidence or generated artifacts still depend on the path;
- worktree lock status and whether portable, network, cloud-synced, or temporarily
  unavailable storage could explain an inaccessible path;
- the exact authorization permitting each proposed cleanup action.

If any result is uncertain, cleanup fails closed to `CLEANUP_BLOCKED`.

## 10. Preservation-First Cleanup Sequence

The normal sequence is:

1. **Capture the complete pre-cleanup inventory.** Record worktrees, local refs,
   remote-tracking refs, relevant tags, configured refspecs, remote branch tips,
   locks, paths, branch tips, dirty state, and process-use state before any fetch,
   prune, deletion, or repair action.
2. **Fetch without pruning.** Refresh approved remote state using an explicit
   no-prune mode. Do not prune tags, remote-tracking refs, or worktree metadata.
3. **Preserve uncertain or unique identities.** Record immutable SHAs and, where
   necessary, create an authorized preservation ref, tag, bundle, patch, or other
   recovery artifact before any action that could remove discoverability.
4. **Verify the exact pull request and integration result.** Record the reviewed
   head, merge identity, default-branch identity, reachability, and any patch-
   equivalence evidence.
5. **Verify post-merge validation and worktree safety.** Record validation status,
   dirty/untracked state, evidence dependencies, lock/storage state, and process
   use. Stop or relocate processes only when separately authorized.
6. **Remove the exact linked worktree without force** when all preconditions pass.
   Do not manually delete its directory first.
7. **Preview worktree metadata pruning.** Run
   `git worktree prune --dry-run --verbose` or an equivalent read-only preview.
   Review every proposed removal and reconcile locked, portable, network-mounted,
   cloud-synced, or temporarily unavailable worktrees.
8. **Prefer target-specific repair.** Use target-specific `git worktree repair`,
   registration correction, or retention when possible. A repository-wide
   metadata prune may run only if every proposed entry is understood and within
   the cleanup authorization. Any unrelated proposed removal requires separate
   authorization or blocks the prune.
9. **Delete the local branch with `git branch -d`** only after integration proof
   and worktree removal are complete.
10. **Resolve the remote branch separately.** Delete, retain, or defer it only
    under the remote-branch policy and exact authority.
11. **Preview remote-tracking-reference pruning.** Use `git remote prune --dry-run
    <remote>` or an equivalent scoped preview after preservation and integration
    proof. Record every proposed removed reference and its former SHA.
12. **Execute scoped reference pruning only when authorized.** Do not use a broad
    fetch-prune step as a routine precondition. Pruning must be limited to the
    reviewed remote and proposed refs; any unrelated effect blocks execution.
13. **Run a final inventory** and compare it to the preserved pre-cleanup
    inventory.
14. **Write the cleanup, retention, or blocker receipt.** Include every command,
    preview, removed reference, metadata record, disposition, limitation, and
    evidence pointer.

Failure at any step stops the sequence. Later steps must not be forced merely to
obtain a clean inventory.

## 11. Prohibited Routine Actions

Agents must not use the following as routine hygiene mechanisms:

- `git reset --hard`;
- `git clean -fd`, `git clean -fdx`, or equivalent broad deletion;
- `git worktree remove --force`;
- `git branch -D` after `git branch -d` refuses;
- `git fetch --prune` or tag pruning before preservation and integration proof;
- unpreviewed `git worktree prune`;
- unscoped remote-reference pruning;
- force-push to make a branch appear integrated;
- deletion of a dirty worktree;
- deletion of a branch containing unproven unique commits;
- deletion based only on branch age;
- deletion based only on a merged pull-request label or summary claim;
- manual removal of worktree directories before Git worktree reconciliation;
- silent abandonment of a worktree after merge.

A forceful recovery action requires explicit operator authorization, a
preservation plan, and a recovery receipt.

## 12. Remote Branch and Reference Policy

Local worktree removal, local branch deletion, remote branch deletion,
remote-tracking-reference pruning, and tag pruning are separate actions.

Remote branch deletion requires one of:

- explicit operator authorization for the work item;
- an accepted repository rule enabling automatic head-branch deletion after
  merge, with protected and retained branches excluded;
- a later accepted hygiene policy that defines deterministic eligibility and
  recovery evidence.

Remote branches associated with open pull requests, unique commits, releases,
hotfix retention, or unresolved findings must be preserved.

Reference pruning requires a pre-prune inventory, preservation of former SHAs, a
scoped preview, and exact authority. It must not be used to erase unresolved
remote disposition evidence.

## 13. Cleanup, Retention, or Blocker Receipt

Every completed, retained, deferred, or blocked reconciliation must produce a
durable receipt containing:

```yaml
schema_version: 1
receipt_id: <stable-id>
goal_id: <goal-id-or-null>
work_item_id: <work-item-id-or-null>
issue: <issue-number-or-null>
pull_request: <pr-number-or-null>
branch_id: <stable-id-or-null>
worktree_id: <stable-id-or-null>
worktree_path: <path-or-null>
local_branch: <name-or-null>
remote_name: <name-or-null>
remote_branch: <name-or-null>
branch_tip_before: <sha-or-null>
origin_main_at_check: <sha>
merge_commit: <sha-or-null>
reviewed_head_sha: <sha-or-null>
post_merge_validation:
  status: passed | not-required-authorized | failed | not-available
  evidence: <path-or-url-or-null>
  waiver_authorization_id: <id-or-null>
integration_proof: reachable | patch-equivalent | retained | blocked | not-applicable
pre_cleanup_inventory: <path-or-record-id>
preservation_artifacts: []
worktree_dirty_before: true | false | not-applicable | not-available
process_check: clear | blocked | not-applicable | not-available
worktree_metadata_preview: []
worktree_metadata_removed: []
remote_prune_preview: []
remote_tracking_refs_removed: []
local_branch_disposition: deleted | retained | deferred | blocked | not-applicable
remote_branch_disposition: deleted | retained | deferred | blocked | not-applicable
worktree_disposition: removed | retained | deferred | blocked | not-applicable
disposition_reason: <required-for-retained-deferred-or-blocked>
next_review_at: <required-for-retained-deferred-or-blocked-or-null>
commands_or_checks: []
final_inventory: <path-or-record-id>
completed_at: <timestamp>
executor: <identity>
authorization_id: <id>
findings: []
limitations: []
```

A receipt may cover a branch-only, remote-only, detached, orphaned, or retained
record by using `null` or `not-applicable` only where the schema permits. Reasons
and next-review conditions are mandatory for retained, deferred, and blocked
dispositions.

Receipts must not contain credentials, tokens, or sensitive process data.

## 14. Inventory and Reconciliation

Until Phase C automation exists, agents must include the following in material
closeout reports:

- pre-action `git worktree list --porcelain` summary;
- relevant local branch names, tips, upstreams, and containment;
- relevant remote branch and remote-tracking-ref inventory;
- dirty worktree findings;
- lock, storage-availability, and process-use findings;
- retained, deferred, or blocked items and reasons;
- post-action comparison and receipt.

Phase C must implement deterministic inventory and reconciliation capable of:

- linking branch and worktree entities to goals, work items, issues, and pull
  requests;
- representing branch-only, remote-only, detached, orphaned, retained, and
  multiple-entity work items;
- validating allowed lifecycle transitions and transition authority;
- detecting orphaned, dirty, merged, blocked, and retained state;
- producing proposed actions without destructive defaults;
- previewing every prune operation;
- executing only explicitly authorized actions;
- producing machine-readable receipts.

## 15. Staleness and Escalation

A worktree or branch is stale when it has exceeded the repository's configured
activity threshold and lacks an active review, authorization, or retention
decision. Age alone is not deletion proof.

Stale items must be classified and surfaced to the operator. They remain
preserved until integration, retention, or cleanup eligibility is proven.

## 16. Phase Mapping

- **Phase A:** adopt this policy and the completion invariant; do not clean
  existing Git state.
- **Phase B:** exercise the full lifecycle on the pilot goal, including separate
  branch/worktree identities, preservation-first sequencing, and at least one
  cleanup, retention, or blocker receipt.
- **Phase C:** implement the registry, transition validator, semantic validator,
  reconciliation tool, prune previews, and appropriate GitHub branch-deletion
  and ruleset controls.
- **Phase D:** publish hygiene status in the generated control-plane dashboard and
  eliminate redundant manual inventories.
- **Phase E:** verify every approved harness follows the same creation,
  preservation, cleanup, transition, and receipt contract.

## 17. Acceptance Criteria

| ID | Criterion |
|---|---|
| `AC-GIT-HYGIENE-001` | Every new non-canonical branch and worktree is registered before substantive editing |
| `AC-GIT-HYGIENE-002` | Initial registrations use `REGISTERED` and all transitions record authority and evidence |
| `AC-GIT-HYGIENE-003` | Branch-only, remote-only, detached, orphaned, retained, and multiple-entity cases are representable |
| `AC-GIT-HYGIENE-004` | Merge transitions work to `MERGED_PENDING_CLEANUP`, not directly to `CLOSED` |
| `AC-GIT-HYGIENE-005` | Dirty or uniquely committed work is preserved and blocks automatic deletion |
| `AC-GIT-HYGIENE-006` | Pre-cleanup inventory and preservation occur before any pruning |
| `AC-GIT-HYGIENE-007` | Worktree metadata and remote-reference pruning are previewed, scoped, and separately authorized |
| `AC-GIT-HYGIENE-008` | Normal cleanup uses non-force worktree removal and `git branch -d` |
| `AC-GIT-HYGIENE-009` | Remote branch deletion is independently authorized or policy-controlled |
| `AC-GIT-HYGIENE-010` | Receipts record post-merge validation and reasons/review conditions for retained, deferred, or blocked state |
| `AC-GIT-HYGIENE-011` | Phase C validation detects orphaned, blocked, and unresolved hygiene state |
| `AC-GIT-HYGIENE-012` | All approved harnesses pass the lifecycle conformance scenario |

## 18. Finding Reconciliation

This revision addresses the independent-review findings:

- `PR318-REV-F-001` — preservation and integration proof now precede all pruning;
- `PR318-REV-F-002` — worktree metadata pruning requires dry-run preview,
  lock/storage review, target-specific reconciliation, and separate authority for
  unrelated entries;
- `PR318-REV-F-003` — deterministic branch/worktree identity, transition, and
  receipt contracts are defined.

## 19. Current Disposition

**Disposition:** `PROPOSED — CORRECTED AFTER INDEPENDENT REVIEW`

**Next Gate:** Fresh independent review of this policy together with ADR-019,
the migration plan, the Phase A evidence record, and the corrected Drive notice
against the exact current pull-request head SHA.
