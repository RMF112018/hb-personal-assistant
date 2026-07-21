---
title: "GitHub-First Control-Plane Migration Plan"
artifact_id: "PLAN-GITHUB-FIRST-CONTROL-PLANE-001"
classification: "Plans"
artifact_type: "Implementation and Migration Plan"
version: "0.1"
status: "Proposed — Phase A in progress"
date_created: "2026-07-21"
date_updated: "2026-07-21"
owner: "Bobby Fetting"
repository: "RMF112018/hb-personal-assistant"
tracking_issue: "#317"
related_adr: "ADR-019"
---

# GitHub-First Control-Plane Migration Plan

## Objective

Move active multi-agent engineering control from the Google Drive Software Delivery Control Center to a GitHub-first hybrid while preserving AEOS governance, operator authorization, independent review, durable evidence, and all existing Workspace history.

## Target Operating Model

| Information | Canonical location |
|---|---|
| Source code and repository governance | Git repository |
| Goal and work-item tracking | GitHub issues and linked/sub-issues |
| Active branch, base SHA, head SHA, and PR | GitHub |
| Independent review | GitHub review or required check bound to the exact PR head |
| Small evidence and manifests | Repository `docs/evidence/` |
| Large evidence packages | GitHub Actions artifacts, releases, or approved external storage with repository manifest |
| Runtime truth | Deployed environment and runtime evidence |
| Human-readable publication and external handoff | Google Drive |
| Final authorization and risk acceptance | Operator |

## Global Constraints

- Preserve the existing Google Drive Workspace and stable Drive identities.
- Do not delete or relocate historical artifacts as part of the initial migration.
- Do not treat Drive publication failure as a canonical engineering-state failure.
- Do not treat GitHub merge as deployment or production authorization.
- Maintain implementer/reviewer separation.
- Bind review claims to exact repository identities.
- Reuse the active `GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001` for the Phase B pilot.
- Keep Phase A reversible and non-runtime-affecting.

## Phase A — Authority Decision

### Purpose

Resolve split authority before migrating any active goal.

### Deliverables

- `docs/decisions/ADR-019-github-first-engineering-control-plane.md`
- Updated `AGENTS.md`
- Updated `AI_OPERATING_MANUAL.md`
- Corrected `CLAUDE.md`
- GitHub issue #317
- Phase A pull request
- Non-canonical Drive authority notice
- Updated Drive bootstrap, manifest, and operating instructions

### Required Actions

1. Establish four explicit authority categories:
   - engineering execution;
   - runtime;
   - publication/reference;
   - final operator decision.
2. Freeze creation of new Drive-native mechanisms that independently track active engineering state.
3. Preserve current Drive records and the active permanent-identity goal unchanged.
4. Correct stale repository guidance that could misroute agent validation.
5. Open a reviewable pull request; do not merge without independent review and operator authorization.

### Completion Gate

- Repository ADR and governance changes are merged.
- Drive identifies itself as publication/reference for repository execution.
- Existing Drive artifacts remain intact.
- No Phase B goal conversion has occurred.
- No runtime, deployment, credential, data, or production changes occurred.

### Rollback

Revert the Phase A repository commit and remove or supersede the Drive notice. No historical Drive data is deleted.

## Phase B — Pilot One Goal

### Pilot

`GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001`

### Purpose

Prove the target model against a real, complex, already-governed workstream without migrating every active item.

### Required Actions

1. Create or nominate a parent GitHub issue for the goal.
2. Map existing work items to GitHub sub-issues or linked issues.
3. Inventory the current Drive goal package and preserve its hashes and stable IDs.
4. Define a minimal state schema containing only current state and pointers.
5. Move historical narrative into append-only events and immutable checkpoints.
6. Bind the active branch and pull request to the goal issue.
7. Represent authorization as a structured, exact work-item and SHA-scoped record.
8. Publish independent review against the exact PR head SHA.
9. Generate a read-only Drive summary linking canonical records.
10. Compare agent retrieval cost and operator effort against the current model.

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
  evidence_manifest: <path>
```

### Completion Gate

- One goal completes at least one governed state transition using the GitHub-first model.
- Current state is deterministically resolvable without reading the full Drive history.
- Review is bound to the exact current head.
- Drive publication is generated or manually published from canonical GitHub/repository state.
- No historical goal evidence is lost.

### Rollback / Recovery

Retain all pilot events. Restore the prior Drive pointer as active only through an explicit operator decision. Prefer forward correction of pointer inconsistencies over deleting pilot records.

## Phase C — Enforcement

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
8. Add instruction-drift checks across root governance and actual repository structure.
9. Add an active branch/worktree registry.
10. Configure a main-branch ruleset with required pull request, required checks, resolved conversations, and stale-review handling.

### Completion Gate

- The semantic validator fails closed on intentionally corrupted fixtures.
- Required checks execute on a pilot PR.
- A changed head invalidates the prior current-head review.
- Main cannot be merged through the normal path without the selected checks.
- Ruleset administration and bypass authority are documented.

## Phase D — Consolidation

### Purpose

Remove redundant manual Workspace maintenance after GitHub-first operation is proven.

### Required Actions

1. Generate a concise Workspace dashboard from repository/GitHub state.
2. Replace manual triple-entry synchronization across source index, current state, and changelog.
3. Convert historical goal changes to append-only events and immutable checkpoints.
4. Organize sequential reviews by goal/work item and publish a current disposition pointer.
5. Archive superseded Workspace generations without deleting evidence.
6. Retain only the Drive documents needed for bootstrap, publication, external review, reports, exports, and historical archive.
7. Prohibit native Google Docs from serving as byte-identical canonical `.md`, `.yaml`, or `.json` objects.

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

This is a target classification model, not authorization to rename or move current folders during Phase A.

### Completion Gate

- Current repository state is no longer manually maintained in three separate Drive ledgers.
- Generated summaries identify their source issue, PR, SHA, and generation time.
- Historical Drive artifacts remain retrievable.
- Cross-platform users can still locate current canonical records.

## Phase E — Cross-Platform Validation

### Purpose

Verify that the target model works consistently across all approved harnesses.

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
- evidence manifest;
- next gate;
- prohibited actions.

### Required Outputs

- Structured conformance result per harness.
- Differences and inaccessible sources.
- Context size and retrieval-step measurements.
- Safety and authorization interpretation results.
- Final migration audit and disposition.

### Completion Gate

- All approved harnesses resolve the same canonical state or fail closed with a documented adapter limitation.
- No harness treats Drive publication as independent execution authorization.
- Residual risks are accepted, remediated, or explicitly deferred by the operator.

## Workstream Tracking

The canonical migration backlog is GitHub issue #317. Phase-specific issues may be created as child or linked work items during implementation. Drive copies are publication artifacts only.

## Validation Strategy

For each phase, capture:

- base and head SHAs;
- files and settings changed;
- commands and checks run;
- exact result scope and exclusions;
- Drive IDs modified or created;
- artifacts preserved;
- deviations and limitations;
- independent review disposition;
- operator authorization for the next phase.

## Current Disposition

**Phase A:** `IN PROGRESS — PROPOSED CHANGES ON REVIEW BRANCH`  
**Phase B:** `NOT STARTED — PILOT RESERVED`  
**Phase C:** `NOT STARTED`  
**Phase D:** `NOT STARTED`  
**Phase E:** `NOT STARTED`

**Next Gate:** Complete the Phase A repository and Drive changes, open the pull request, and obtain an independent review against the exact PR head.
