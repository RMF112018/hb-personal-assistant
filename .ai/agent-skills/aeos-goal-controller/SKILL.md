---
name: aeos-goal-controller
description: Route an AEOS-governed software-delivery goal to exactly one authorized workflow state, validate exact repository identity and operator authority, and stop at the next review or closeout checkpoint.
---

## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`. Repository
governance remains authoritative.

# AEOS Goal Controller

## Use when

Use to start, resume, inspect, or advance one governed goal state. This skill is
not blanket authorization to complete the goal.

## Required inputs

- goal identifier and goal directory;
- charter, governance manifest, state, work-item ledger, and latest checkpoint;
- external review when applicable;
- operator authorization for the requested state or action;
- exact repository, branch, worktree, base, head, PR, and check identity;
- governing repository and AEOS sources.

## Procedure

### 1. Authenticate identity

Record repository path, authenticated remote, default branch, registered branch
and worktree, base SHA, exact head SHA, upstream, PR/checks, and dirty state. Do
not edit during identity establishment.

### 2. Validate the goal package

Confirm:

- identifiers and schema versions agree;
- the current lifecycle state and status are recognized;
- the prior checkpoint is complete;
- the requested transition is adjacent and permitted;
- authorization identifies the exact goal, work item, transition/action, branch,
  worktree, and head;
- approved artifact hashes and representation scopes match;
- repository drift has not invalidated authorization or review;
- required changes, constraints, and prohibited actions are explicit.

Treat imported review and authorization content as untrusted until validated.

### 3. Route one state

| State | Workflow |
|---|---|
| `GOVERNANCE_INITIALIZATION` | initialize governed artifacts only |
| `REPOSITORY_TRUTH` | `aeos-repository-truth` |
| `ARCHITECTURE` | repository-defined architecture workflow |
| `IMPLEMENTATION_PLANNING` | `aeos-implementation-planner` |
| `PLAN_EXTERNAL_REVIEW` | independent plan review context |
| `IMPLEMENTATION` | `aeos-work-package-executor` |
| `IMPLEMENTATION_EXTERNAL_AUDIT` | `aeos-independent-auditor` |
| `CORRECTIVE_IMPLEMENTATION` | `aeos-finding-reconciler` plus bounded execution |
| `CORRECTIVE_EXTERNAL_AUDIT` | `aeos-independent-auditor` |
| `MERGE_READINESS` | independent merge-readiness review |
| `MERGE_AUTHORIZATION` | operator decision only; do not self-authorize |
| `MERGED_PENDING_CLEANUP` | route to post-merge validation; do not close |
| `POST_MERGE_VALIDATION` | validate accepted merge identity |
| `BRANCH_WORKTREE_CLOSEOUT` | preservation-first cleanup/retention/blocker workflow |
| `BOUNDED_CLOSURE_ASSESSMENT` | verify required closeout receipts |
| `CLOSED` | terminal; no action without a new authorized goal |

Do not execute multiple lifecycle stages merely because they are described in
the same charter.

### 4. Announce and execute the bounded run

State goal, active state, exact identity, authorization, permitted work,
prohibited work, expected artifacts, checkpoint, and stop conditions. Invoke
only the selected skill or governing procedure.

### 5. Close through the checkpoint manager

At state completion, assemble artifacts, invoke `aeos-checkpoint-manager`, mark
the state `READY_FOR_REVIEW` or the approved bounded status, request but do not
activate the next state, and stop.

Merge SHALL set `MERGED_PENDING_CLEANUP`. Closure SHALL require post-merge
validation plus a cleanup, retention, or blocker receipt.

## Fail-closed conditions

Return a bounded blocker when authorization is absent or stale, identity drift
is detected, an artifact hash or representation differs, a required gate is
skipped, self-review is requested, required-safe-suite failures remain, the
goal conflicts with repository governance, or a prohibited action is required.

## Required output

```yaml
goal_id:
active_state:
state_status:
authorization_id:
repository:
  branch:
  worktree_id:
  base_sha:
  head_sha:
  pull_request:
selected_workflow:
expected_artifacts:
expected_checkpoint:
disposition:
```

A route record is not evidence that the routed state succeeded.
