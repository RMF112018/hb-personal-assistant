---
title: "GitHub-First Control-Plane Migration Plan"
artifact_id: "PLAN-GITHUB-FIRST-CONTROL-PLANE-001"
classification: "Plans"
artifact_type: "Implementation and Migration Plan"
version: "0.3"
status: "Proposed — Phase A corrected after independent review"
date_created: "2026-07-21"
date_updated: "2026-07-21"
owner: "Bobby Fetting"
repository: "RMF112018/hb-personal-assistant"
tracking_issue: "#317"
related_adr: "ADR-019"
related_policy: "POL-GIT-HYGIENE-001"
---

# GitHub-First Control-Plane Migration Plan

## Objective

Move active multi-agent engineering control from the Google Drive Software
Delivery Control Center to a GitHub-first hybrid while preserving AEOS
governance, operator authorization, independent review, durable evidence,
existing Workspace history, and safe branch/worktree lifecycle management.

## Target Operating Model

| Information | Canonical location |
|---|---|
| Source code and repository governance | Git repository |
| Goal and work-item tracking | GitHub issues and linked/sub-issues |
| Active branch, base SHA, head SHA, and PR | GitHub |
| Branch/worktree registration and lifecycle | Repository registry plus local Git evidence |
| Independent review | GitHub review or required check bound to the exact PR head |
| Cleanup, retention, and blocker receipts | Repository evidence path linked to the work item |
| Small evidence and manifests | Repository `docs/evidence/` |
| Large evidence packages | GitHub Actions artifacts, releases, or approved external storage with repository manifest |
| Runtime truth | Deployed environment and runtime evidence |
| Human-readable publication and external handoff | Google Drive |
| Final authorization and risk acceptance | Operator |

## Global Constraints

- Preserve the existing Google Drive Workspace and stable Drive identities.
- Do not delete or relocate historical artifacts during initial migration.
- Do not treat Drive publication failure as a canonical engineering-state failure.
- Do not treat GitHub merge as deployment, production authorization, or work-item
  closeout.
- Maintain implementer/reviewer separation.
- Bind review claims to exact repository identities.
- Reuse `GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001` for the Phase B
  pilot only after separate authorization.
- Keep Phase A reversible and non-runtime-affecting.
- Do not delete existing branches, worktrees, remote branches, or reference
  evidence during Phase A.
- Preserve dirty, untracked, uniquely committed, process-dependent, inaccessible,
  locked, or uncertain work.
- Treat worktree removal, local branch deletion, remote branch deletion,
  remote-tracking-reference pruning, and metadata pruning as separate actions.
- Capture and preserve pre-cleanup identity before any prune operation.
- Do not use force-based Git cleanup as routine hygiene.

## Governing Hygiene Lifecycle

The canonical policy is:

```text
docs/governance/branch-worktree-lifecycle-policy.md
```

The normal lifecycle is:

```text
REGISTERED
→ ACTIVE
→ REVIEW_PENDING
→ CHANGES_REQUESTED, when required
→ MERGED_PENDING_CLEANUP
→ CLEANUP_VERIFIED | RETAINED_BY_DECISION | CLEANUP_BLOCKED
→ CLOSED, when every linked entity is reconciled
```

Every transition must record entity identity, from/to state, timestamp, actor,
authority, evidence, and reason. Any unresolved dirty state, unique commits,
process use, inaccessible storage, uncertain integration proof, or missing
authorization results in `CLEANUP_BLOCKED` rather than deletion.

## Phase A — Authority Decision and Hygiene Contract

### Purpose

Resolve split authority and define safe repository closeout rules before
migrating any active goal or cleaning existing Git state.

### Deliverables

- `docs/decisions/ADR-019-github-first-engineering-control-plane.md`
- `docs/governance/branch-worktree-lifecycle-policy.md`
- `docs/evidence/github-first-control-plane-phase-a/phase-a-repository-hygiene-evidence.md`
- Updated `AGENTS.md`
- Updated `AI_OPERATING_MANUAL.md`
- Corrected `CLAUDE.md`
- GitHub issue #317
- Phase A pull request #318
- Non-canonical Drive authority notice
- Updated Drive bootstrap, manifest, source index, and operating instructions

### Required Actions

1. Establish four explicit authority categories:
   - engineering execution;
   - runtime;
   - publication/reference;
   - final operator decision.
2. Freeze creation of new Drive-native mechanisms that independently track active
   engineering state.
3. Preserve current Drive records and the permanent-identity pilot goal unchanged.
4. Correct stale repository guidance that could misroute validation.
5. Adopt separate branch/worktree identity records and allowed lifecycle
   transitions.
6. Establish that merge results in `MERGED_PENDING_CLEANUP`, not immediate
   closure.
7. Require preservation-first cleanup sequencing and prohibit prune-before-proof.
8. Require scoped preview and separate authority for worktree metadata and remote
   reference pruning.
9. Define cleanup receipts that include post-merge validation and reasons/review
   conditions for retained, deferred, or blocked dispositions.
10. Record a bounded Phase A non-cleanup evidence assessment, including unavailable
    local-state evidence.
11. Open a reviewable pull request; do not merge without fresh independent review
    and operator authorization.

### Completion Gate

- Repository ADR, policy, evidence record, and governance changes are merged.
- Drive identifies itself as publication/reference for repository execution.
- The Drive notice identifies the exact current review head or explicitly marks a
  prior head superseded.
- Existing Drive artifacts remain intact.
- No Phase B goal conversion has occurred.
- No existing branch, worktree, remote branch, or reference evidence has been
  deleted under Phase A.
- The evidence record truthfully classifies the no-cleanup claim as verified,
  partially verified, or unavailable based on accessible evidence.
- Root governance requires branch/worktree disposition before work-item closure.
- No runtime, deployment, credential, data, or production changes occurred.

### Rollback

Revert the Phase A repository commit and remove or supersede the Drive notice. No
historical Drive data or existing Git work is deleted.

## Phase B — Pilot One Goal and Full Lifecycle

### Pilot

`GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001`

### Purpose

Prove the target model and the complete preservation-first lifecycle against a
real governed workstream without migrating every active item.

### Required Actions

1. Create or nominate a parent GitHub issue for the goal.
2. Map existing work items to GitHub sub-issues or linked issues.
3. Inventory the current Drive goal package and preserve hashes and stable IDs.
4. Define a minimal goal state containing only current state and pointers.
5. Move historical narrative into append-only events and immutable checkpoints.
6. Create separate branch and worktree registrations using stable identities.
7. Represent branch-only, remote-only, detached, orphaned, retained, and multiple-
   entity cases deterministically.
8. Bind branch, worktree, PR, authorization, review, evidence, and checkpoint to
   exact identities.
9. Record each lifecycle transition and authority.
10. Publish independent review against the exact PR head SHA.
11. After authorized merge, transition linked entities to
    `MERGED_PENDING_CLEANUP`.
12. Perform or explicitly waive post-merge validation under exact authority.
13. Capture complete pre-cleanup worktree/ref/refspec/remote inventory.
14. Fetch without pruning.
15. Preserve unique or uncertain branch tips and recovery artifacts.
16. Prove integration or patch equivalence.
17. Check dirty state, locks, inaccessible storage, process use, and evidence
    dependencies.
18. Remove only the exact eligible worktree without force.
19. Preview worktree metadata pruning and block unrelated proposed removals.
20. Delete eligible local branches with `git branch -d`.
21. Resolve remote branch disposition under separate authority.
22. Preview and, only when authorized, execute scoped remote-reference pruning.
23. Produce a machine-readable cleanup, retention, or blocker receipt and final
    inventory.
24. Generate a read-only Drive summary linking canonical records.
25. Compare retrieval cost, operator effort, and hygiene outcomes against the
    prior model.

### Minimal Goal State Target

```yaml
schema_version: 2
goal_id: GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001
lifecycle_state: IMPLEMENTATION
status: IN_PROGRESS
repository:
  full_name: RMF112018/hb-personal-assistant
  branch: <branch>
  base_sha: <sha>
  head_sha: <sha>
active_work_item_id: <work-item>
authorization_id: <authorization>
checkpoint_id: <checkpoint>
next_gate: <gate>
updated_at: <timestamp>
pointers:
  goal_issue: <number>
  implementation_pr: <number>
  branch_registration: <path-or-id>
  worktree_registration: <path-or-id-or-null>
  evidence_manifest: <path>
  cleanup_receipt: <path-or-null>
```

### Branch Registration Contract

```yaml
branch_id: <stable-id>
local_branch: <name-or-null>
remote_name: origin | <other-or-null>
remote_branch: <name-or-null>
remote_tracking_ref: <ref-or-null>
branch_tip_sha: <sha>
work_item_id: <id-or-null>
lifecycle_state: REGISTERED
expected_disposition: remove-after-merge | retain-by-decision | investigate
retention_reason: <reason-or-null>
next_review_at: <timestamp-or-null>
```

### Worktree Registration Contract

```yaml
worktree_id: <stable-id>
absolute_path: <path>
branch_id: <stable-id-or-null>
detached_head_sha: <sha-or-null>
work_item_id: <id-or-null>
lifecycle_state: REGISTERED
locked: true | false | unknown
storage_class: local | portable | network | cloud-synced | unknown
expected_disposition: remove-after-merge | retain-by-decision | investigate
```

### Required Pilot Evidence

- initial `git worktree list --porcelain` inventory;
- local refs, remote-tracking refs, tags, fetch refspecs, and relevant remote branch
  tips;
- branch and worktree registrations;
- transition records;
- base and head SHA history;
- exact reviewed head SHA;
- merge identity;
- post-merge validation result or exact waiver;
- preservation artifacts for unique or uncertain work;
- pre-cleanup dirty, lock/storage, process-use, and integration proof;
- worktree-prune dry-run output and review;
- remote-prune dry-run output and review;
- cleanup commands and exit results;
- final inventory comparison;
- cleanup, retention, or blocker receipt.

### Completion Gate

- One goal completes at least one governed state transition using the GitHub-first
  model.
- Current state is deterministically resolvable without reading the full Drive
  history.
- Review is bound to the exact current head.
- Branch-only, worktree, detached, retained, or blocked states are represented
  without ambiguity.
- The pilot completes or explicitly blocks the preservation-first lifecycle.
- At least one machine-readable cleanup, retention, or blocker receipt is
  produced.
- No prune action occurs before inventory and preservation.
- No force-based cleanup is used.
- Drive publication is generated or manually published from canonical state.
- No historical goal evidence or uncertain local Git work is lost.

### Rollback / Recovery

Retain all pilot events and receipts. Restore the prior Drive pointer as active
only through explicit operator decision. Preserve a branch or worktree whenever
proof is incomplete. Prefer forward correction of pointer and registry
inconsistencies over deleting uncertain work.

## Phase C — Enforcement and Reconciliation

### Purpose

Convert the pilot conventions into deterministic controls.

### Required Actions

1. Add `aeos-control-plane validate` or an equivalent canonical command.
2. Validate goal state against a restrictive schema.
3. Validate issue, authorization, branch, worktree, base SHA, head SHA, and PR
   identities.
4. Validate reviewer independence and reviewed head SHA.
5. Invalidate stale reviews when head changes.
6. Reconcile PR state, goal lifecycle state, branch state, and worktree state.
7. Add instruction-drift checks across root governance and actual structure.
8. Implement canonical branch, worktree, transition, and receipt registries.
9. Validate allowed transitions and transition authority.
10. Represent branch-only, remote-only, detached, orphaned, retained, blocked, and
    multiple-entity work items.
11. Implement deterministic inventory and dry-run reconciliation.
12. Capture inventory before fetch or prune and use fetch-without-prune.
13. Require preservation and integration proof before proposing cleanup.
14. Preview worktree metadata pruning and require review of every proposed entry.
15. Prefer target-specific repair; require separate authority for unrelated
    metadata effects.
16. Preview remote-reference pruning and record former SHAs.
17. Execute cleanup and pruning only under exact authorization.
18. Produce receipts and preserve failed or blocked attempts.
19. Add the cleanup closeout gate to the goal/work-item controller.
20. Configure a main-branch ruleset with required PRs, checks, resolved
    conversations, and stale-review handling.
21. Decide and document GitHub automatic head-branch deletion policy.

### Suggested Command Surface

```bash
python .ai/aeos/bin/aeos_git_hygiene.py inventory
python .ai/aeos/bin/aeos_git_hygiene.py reconcile --dry-run
python .ai/aeos/bin/aeos_git_hygiene.py cleanup --authorization <id>
```

Inventory, proposed reconciliation, and authorized execution must remain
separate commands or modes.

### Completion Gate

- Semantic validation fails closed on corrupted fixtures.
- Required checks execute on a pilot PR.
- A changed head invalidates the prior current-head review.
- Main cannot be merged through the normal path without selected checks.
- Every active branch and worktree resolves to a registry record or finding.
- Allowed transitions and authority are validated.
- Dirty, unique, inaccessible, locked, process-in-use, and uncertain items block
  automatic cleanup.
- Prune previews identify every proposed effect before execution.
- Unrelated proposed metadata/reference removals require separate authorization.
- An eligible merged worktree can be removed without force and produces a valid
  receipt.
- Ruleset, branch deletion, pruning, cleanup, and bypass authority are documented.

## Phase D — Consolidation and Dashboard

### Purpose

Remove redundant manual Workspace maintenance and make unresolved repository
hygiene visible after GitHub-first operation is proven.

### Required Actions

1. Generate a concise Workspace dashboard from repository/GitHub state.
2. Replace manual triple-entry synchronization across source index, current state,
   and changelog.
3. Convert goal history to append-only events and immutable checkpoints.
4. Organize sequential reviews by goal/work item and publish a current disposition
   pointer.
5. Archive superseded Workspace generations without deleting evidence.
6. Retain only Drive documents needed for bootstrap, publication, external review,
   reports, exports, and archive.
7. Prohibit native Google Docs from serving as byte-identical canonical `.md`,
   `.yaml`, or `.json` objects.
8. Publish branch/worktree identity, owner, work item, lifecycle state, dirty state,
   locks/storage availability, integration proof, cleanup eligibility, prune
   previews, and retained/blocked review conditions.
9. Add operator-facing stale-item review without treating age as deletion proof.

### Proposed Drive End State

```text
00_READ_ME
10-Published-Governance
20-Published-Architecture
30-Published-Plans
40-External-Review-Packages
50-Reports
90-Exports
99-Archive
```

This is a target classification model, not authorization to rename or move
current folders during Phase A.

### Completion Gate

- Current repository state is no longer manually maintained in three separate
  Drive ledgers.
- Generated summaries identify source issue, PR, SHA, and generation time.
- The dashboard identifies active, retained, stale, blocked, branch-only,
  detached, and inaccessible entities.
- Historical Drive artifacts remain retrievable.
- Cross-platform users can locate current canonical records.

## Phase E — Cross-Platform Lifecycle Validation

### Purpose

Verify that the target model and repository-hygiene contract work consistently
across all approved harnesses.

### Harnesses

- Claude Code
- Codex
- Grok
- Composer
- ChatGPT

### Conformance Scenario

Each harness must resolve:

- active goal, lifecycle state, work item, and authorization;
- branch and worktree stable identities and relationships;
- base/head SHAs and implementation PR;
- current review state and reviewed SHA;
- dirty, unique, inaccessible, lock, and process-use requirements;
- preservation and integration proof;
- cleanup and prune authorization boundaries;
- post-merge validation and receipt state;
- next gate and prohibited actions.

Each implementation-capable harness must demonstrate that it:

1. creates or uses only registered entities;
2. starts registrations at `REGISTERED`;
3. records transitions and authority;
4. does not reuse unrelated dirty work;
5. preserves unique or uncertain identities before pruning;
6. treats merge as `MERGED_PENDING_CLEANUP`;
7. previews worktree and remote-reference pruning;
8. does not use force-based cleanup as routine fallback;
9. separates worktree, local-branch, remote-branch, metadata, and reference
   dispositions;
10. produces the same receipt contract.

### Completion Gate

- All approved harnesses resolve the same canonical state or fail closed with a
  documented adapter limitation.
- No harness treats Drive publication as execution authorization.
- No harness treats merge as work-item closure.
- No harness deletes or prunes uncertain evidence before preservation.
- All implementation-capable harnesses conform to registration, transition,
  preview, and receipt contracts.
- Residual risks are accepted, remediated, or explicitly deferred by the operator.

## Workstream Tracking

The canonical migration backlog is GitHub issue #317. Phase-specific issues may
be created as linked work items. Drive copies are publication artifacts only.

## Validation Strategy

For each phase, capture:

- base and head SHAs;
- files and settings changed;
- commands and checks run;
- exact result scope and exclusions;
- Drive IDs modified or created;
- branches, worktrees, refs, and metadata created, retained, removed, or blocked;
- pre-action and post-action inventories;
- prune previews and authorization;
- cleanup, retention, or blocker receipts;
- artifacts preserved;
- deviations and limitations;
- independent review disposition;
- operator authorization for the next phase.

## Independent Review Finding Reconciliation

- `PR318-REV-F-001`: Phase B and Phase C now require inventory, no-prune fetch,
  preservation, and integration proof before any scoped pruning.
- `PR318-REV-F-002`: worktree metadata pruning now requires dry-run preview,
  review of every proposed removal, storage/lock reconciliation, and separate
  authority for unrelated entries.
- `PR318-REV-F-003`: separate branch/worktree identities, allowed transitions,
  branch-only/detached/remote-only representations, post-merge validation fields,
  and retained/deferred/blocked review conditions are now explicit.
- `PR318-REV-F-004`: resolved through the in-place Drive publication update.
- `PR318-REV-F-005`: resolved through a bounded evidence record that states the
  accessible proof and local-state limitations without performing cleanup.

## Current Disposition

**Phase A:** `CORRECTED AFTER REVISE REVIEW — FRESH EXACT-HEAD REVIEW REQUIRED`  
**Phase B:** `NOT STARTED — PILOT RESERVED`  
**Phase C:** `NOT STARTED`  
**Phase D:** `NOT STARTED`  
**Phase E:** `NOT STARTED`

**Next Gate:** Correct the Drive notice, verify CI against the corrected head, and
obtain a fresh independent review of PR #318. No cleanup or Phase B work is
authorized by this plan.
