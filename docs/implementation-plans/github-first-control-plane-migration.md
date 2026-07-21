---
title: "GitHub-First Control-Plane Migration Plan"
artifact_id: "PLAN-GITHUB-FIRST-CONTROL-PLANE-001"
classification: "Plans"
artifact_type: "Implementation and Migration Plan"
version: "0.2"
status: "Proposed — Phase A amended in PR #318"
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
governance, operator authorization, independent review, durable evidence, all
existing Workspace history, and safe branch/worktree lifecycle management.

## Target Operating Model

| Information | Canonical location |
|---|---|
| Source code and repository governance | Git repository |
| Goal and work-item tracking | GitHub issues and linked/sub-issues |
| Active branch, base SHA, head SHA, and PR | GitHub |
| Local worktree registration and lifecycle | Repository machine-readable registry plus local Git evidence |
| Independent review | GitHub review or required check bound to the exact PR head |
| Branch/worktree cleanup receipts | Repository goal/checkpoint evidence or approved machine-readable evidence path |
| Small evidence and manifests | Repository `docs/evidence/` |
| Large evidence packages | GitHub Actions artifacts, releases, or approved external storage with repository manifest |
| Runtime truth | Deployed environment and runtime evidence |
| Human-readable publication and external handoff | Google Drive |
| Final authorization and risk acceptance | Operator |

## Global Constraints

- Preserve the existing Google Drive Workspace and stable Drive identities.
- Do not delete or relocate historical artifacts as part of the initial migration.
- Do not treat Drive publication failure as a canonical engineering-state failure.
- Do not treat GitHub merge as deployment, production authorization, or work-item
  closeout.
- Maintain implementer/reviewer separation.
- Bind review claims to exact repository identities.
- Reuse the active `GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001`
  for the Phase B pilot.
- Keep Phase A reversible and non-runtime-affecting.
- Do not delete existing branches or worktrees during Phase A.
- Preserve dirty, untracked, uniquely committed, or uncertain work.
- Treat local worktree removal, local branch deletion, and remote branch deletion
  as separate actions.
- Do not use force-based Git cleanup as routine hygiene.

## Governing Hygiene Lifecycle

The canonical policy is:

```text
docs/governance/branch-worktree-lifecycle-policy.md
```

The minimum lifecycle is:

```text
REGISTERED
→ ACTIVE
→ REVIEW_PENDING
→ CHANGES_REQUESTED, when required
→ MERGED_PENDING_CLEANUP
→ CLEANUP_VERIFIED or RETAINED_BY_DECISION
→ CLOSED
```

Any unresolved dirty state, unique commits, process use, uncertain integration
proof, or missing authorization results in `CLEANUP_BLOCKED` rather than
deletion.

## Phase A — Authority Decision and Hygiene Contract

### Purpose

Resolve split authority and define repository closeout rules before migrating any
active goal or cleaning existing Git state.

### Deliverables

- `docs/decisions/ADR-019-github-first-engineering-control-plane.md`
- `docs/governance/branch-worktree-lifecycle-policy.md`
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
2. Freeze creation of new Drive-native mechanisms that independently track
   active engineering state.
3. Preserve current Drive records and the active permanent-identity goal
   unchanged.
4. Correct stale repository guidance that could misroute agent validation.
5. Adopt branch/worktree registration, lifecycle, fail-closed cleanup, and
   receipt requirements.
6. Establish that merge results in `MERGED_PENDING_CLEANUP`, not immediate
   closure.
7. Explicitly prohibit destructive cleanup of existing local or remote Git state
   during Phase A.
8. Open a reviewable pull request; do not merge without independent review and
   operator authorization.

### Completion Gate

- Repository ADR, policy, and governance changes are merged.
- Drive identifies itself as publication/reference for repository execution.
- Existing Drive artifacts remain intact.
- No Phase B goal conversion has occurred.
- No existing branch, worktree, or remote branch has been deleted under Phase A.
- Root governance requires branch/worktree disposition before work-item closure.
- No runtime, deployment, credential, data, or production changes occurred.

### Rollback

Revert the Phase A repository commit and remove or supersede the Drive notice.
No historical Drive data or existing Git work is deleted.

## Phase B — Pilot One Goal and Full Lifecycle

### Pilot

`GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001`

### Purpose

Prove the target model and complete repository-hygiene lifecycle against a real,
complex, already-governed workstream without migrating every active item.

### Required Actions

1. Create or nominate a parent GitHub issue for the goal.
2. Map existing work items to GitHub sub-issues or linked issues.
3. Inventory the current Drive goal package and preserve its hashes and stable
   IDs.
4. Define a minimal state schema containing only current state and pointers.
5. Move historical narrative into append-only events and immutable checkpoints.
6. Register the pilot branch and worktree with path, branch, base SHA, owner,
   goal, work item, issue/PR pointers, and expected disposition.
7. Bind the active branch and pull request to the goal issue.
8. Represent authorization as a structured, exact work-item and SHA-scoped
   record.
9. Publish independent review against the exact PR head SHA.
10. After authorized merge, transition to `MERGED_PENDING_CLEANUP`.
11. Perform post-merge validation.
12. Verify the worktree is clean or preserve and assign all remaining material.
13. Prove the branch is integrated, patch-equivalent, retained, or blocked.
14. Check for running processes and evidence dependencies before worktree
    removal.
15. Remove the worktree without force when eligible.
16. Delete the local branch with `git branch -d` when eligible.
17. Delete or defer the remote branch only under separate authorization or an
    accepted automatic-delete policy.
18. Produce a machine-readable cleanup receipt and final Git inventory.
19. Generate a read-only Drive summary linking canonical records.
20. Compare agent retrieval cost, operator effort, and hygiene outcomes against
    the current model.

### Minimal State Target

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
  worktree_registration: <path-or-id>
  evidence_manifest: <path>
  cleanup_receipt: <path-or-null>
```

### Required Pilot Evidence

- initial `git worktree list --porcelain` inventory;
- initial relevant local and remote branch inventory;
- registration record;
- base and head SHA history;
- exact reviewed head SHA;
- merge identity;
- post-merge validation result;
- pre-cleanup dirty-state and integration proof;
- process-use check;
- cleanup commands and exit results;
- final worktree and branch inventory;
- cleanup, retention, or blocker receipt.

### Completion Gate

- One goal completes at least one governed state transition using the GitHub-first
  model.
- Current state is deterministically resolvable without reading the full Drive
  history.
- Review is bound to the exact current head.
- The pilot branch/worktree completes or explicitly blocks the full lifecycle.
- At least one machine-readable cleanup or retention receipt is produced.
- No force-based cleanup is used.
- Drive publication is generated or manually published from canonical
  GitHub/repository state.
- No historical goal evidence or uncertain local Git work is lost.

### Rollback / Recovery

Retain all pilot events and receipts. Restore the prior Drive pointer as active
only through an explicit operator decision. Preserve the branch or worktree when
cleanup proof is incomplete. Prefer forward correction of pointer and registry
inconsistencies over deleting records or uncertain work.

## Phase C — Enforcement and Reconciliation

### Purpose

Convert the pilot conventions into deterministic controls.

### Required Actions

1. Add `aeos-control-plane validate` or an equivalent canonical command.
2. Validate goal state against a restrictive schema.
3. Validate branch, base SHA, head SHA, PR, and issue existence.
4. Validate authorization scope against the active work item.
5. Validate reviewer independence and reviewed head SHA.
6. Invalidate stale reviews when head changes.
7. Reconcile PR state and goal lifecycle state.
8. Add instruction-drift checks across root governance and actual repository
   structure.
9. Implement a canonical branch/worktree registry.
10. Implement deterministic inventory and reconciliation tooling that classifies:
    - canonical checkout;
    - active and review-pending work;
    - merged-pending-cleanup work;
    - dirty work requiring preservation;
    - unique commits;
    - patch-equivalent branches;
    - detached heads;
    - orphaned registrations;
    - process-in-use worktrees;
    - retained and blocked items.
11. Require integration proof before proposing cleanup.
12. Execute cleanup only when explicitly authorized and non-force preconditions
    pass.
13. Produce cleanup receipts and preserve failed/blocked attempts.
14. Add a cleanup closeout gate to the goal/work-item controller.
15. Configure a main-branch ruleset with required pull request, required checks,
    resolved conversations, and stale-review handling.
16. Decide whether GitHub automatic head-branch deletion is enabled and document
    protected/retained exclusions.

### Suggested Command Surface

```bash
python .ai/aeos/bin/aeos_git_hygiene.py inventory
python .ai/aeos/bin/aeos_git_hygiene.py reconcile --dry-run
python .ai/aeos/bin/aeos_git_hygiene.py cleanup --authorization <id>
```

The implementation may use a different canonical command name, but it must keep
inventory, proposed reconciliation, and authorized execution distinct.

### Completion Gate

- The semantic validator fails closed on intentionally corrupted fixtures.
- Required checks execute on a pilot PR.
- A changed head invalidates the prior current-head review.
- Main cannot be merged through the normal path without the selected checks.
- Every active non-canonical worktree resolves to a registry entry or an
  actionable finding.
- Dirty, unique, process-in-use, and uncertain items block automatic cleanup.
- An eligible merged worktree can be removed without force and produces a valid
  receipt.
- Ruleset administration, branch deletion, cleanup execution, and bypass
  authority are documented.

## Phase D — Consolidation and Dashboard

### Purpose

Remove redundant manual Workspace maintenance and make unresolved repository
hygiene visible after GitHub-first operation is proven.

### Required Actions

1. Generate a concise Workspace dashboard from repository/GitHub state.
2. Replace manual triple-entry synchronization across source index, current
   state, and changelog.
3. Convert historical goal changes to append-only events and immutable
   checkpoints.
4. Organize sequential reviews by goal/work item and publish a current
   disposition pointer.
5. Archive superseded Workspace generations without deleting evidence.
6. Retain only the Drive documents needed for bootstrap, publication, external
   review, reports, exports, and historical archive.
7. Prohibit native Google Docs from serving as byte-identical canonical `.md`,
   `.yaml`, or `.json` objects.
8. Add repository-hygiene status to the generated dashboard, including:
   - worktree path and registration;
   - owner or agent;
   - goal, work item, issue, and pull request;
   - lifecycle state;
   - dirty/clean result;
   - last activity and age;
   - integration proof;
   - cleanup eligibility;
   - retained or blocked reason;
   - remote branch disposition.
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
- Generated summaries identify their source issue, PR, SHA, and generation time.
- The dashboard identifies all active, retained, stale, and blocked branches and
  worktrees.
- Historical Drive artifacts remain retrievable.
- Cross-platform users can still locate current canonical records.

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

Each harness receives the same bounded request and must independently resolve:

- active goal;
- active lifecycle state;
- active work item;
- authorization ID and scope;
- repository and branch;
- base and head SHAs;
- implementation PR;
- current review state and reviewed SHA;
- worktree registration and lifecycle state;
- dirty/clean and integration-proof requirements;
- cleanup authorization boundary;
- evidence manifest and cleanup receipt;
- next gate;
- prohibited actions.

Each implementation-capable harness must also demonstrate that it:

1. creates or uses only a registered branch/worktree;
2. does not reuse an unrelated dirty worktree;
3. preserves dirty or unique work;
4. treats merge as `MERGED_PENDING_CLEANUP`;
5. does not use force-based cleanup as a routine fallback;
6. separates worktree, local-branch, and remote-branch disposition;
7. produces the same cleanup receipt contract.

### Required Outputs

- Structured conformance result per harness.
- Differences and inaccessible sources.
- Context size and retrieval-step measurements.
- Safety and authorization interpretation results.
- Branch/worktree lifecycle and receipt results.
- Final migration audit and disposition.

### Completion Gate

- All approved harnesses resolve the same canonical state or fail closed with a
  documented adapter limitation.
- No harness treats Drive publication as independent execution authorization.
- No harness treats merge as automatic work-item closure.
- No harness deletes uncertain, dirty, or uniquely committed work.
- All implementation-capable harnesses conform to the registration and receipt
  contract.
- Residual risks are accepted, remediated, or explicitly deferred by the
  operator.

## Workstream Tracking

The canonical migration backlog is GitHub issue #317. Phase-specific issues may
be created as child or linked work items during implementation. Drive copies are
publication artifacts only.

## Validation Strategy

For each phase, capture:

- base and head SHAs;
- files and settings changed;
- commands and checks run;
- exact result scope and exclusions;
- Drive IDs modified or created;
- worktrees and branches created, retained, removed, or blocked;
- cleanup authorization and receipts;
- artifacts preserved;
- deviations and limitations;
- independent review disposition;
- operator authorization for the next phase.

## Current Disposition

**Phase A:** `IMPLEMENTED ON PR #318 — AMENDED INDEPENDENT REVIEW REQUIRED`  
**Phase B:** `NOT STARTED — PILOT RESERVED`  
**Phase C:** `NOT STARTED`  
**Phase D:** `NOT STARTED`  
**Phase E:** `NOT STARTED`

**Next Gate:** Independently review the exact amended PR #318 head, including
`ADR-019`, `POL-GIT-HYGIENE-001`, root governance changes, and the updated
migration gates. No cleanup or Phase B work is authorized by this plan.
