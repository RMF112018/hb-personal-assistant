---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 10 — AEOS Prompt Entry Points

These prompts initiate a governed mode. They do not replace repository policy,
the Master Index, or explicit authorization.

## Discovery / Repository Truth

```text
Mode: Discovery / Repository Truth
Repository / authenticated remote:
Issue or goal:
Branch / worktree:
Base SHA / expected head:
Objective:

Authenticate repository and GitHub state. Record branch, worktree, base and
exact head, PR/checks when present, dirty state, relevant files, tests,
schemas, migrations, runtime surfaces, verified facts, assumptions, unknowns,
and evidence gaps. When branch/worktree hygiene is material, inventory refs,
tags, locks, and process dependencies without pruning or deleting. Do not
design or implement. Produce a repository-truth report and bounded next gate.
```

## Architecture

```text
Mode: Architecture
Approved objective:
Repository-truth report:
Exact repository identity:
Constraints:

Develop the target architecture. Include components, interfaces, data and trust
boundaries, authorization, failure behavior, observability, alternatives,
invariants, risks, acceptance criteria, and repository-specific lifecycle
implications. Do not begin implementation planning until the architecture is
complete and independently reviewed when required.
```

## Implementation Planning

```text
Mode: Implementation Planning
Approved architecture:
Acceptance criteria:
Repository / branch / worktree / base head:
Authorization:

Produce an executable plan with bounded work packages, branch/worktree
ownership, expected closeout disposition, files/symbols, proportional tests,
failure classification, integrated-green requirements, evidence representation
and hash scope, rollback, prohibited actions, stop conditions, independent
review gates, post-merge validation, and cleanup/retention/blocker requirements.
Do not implement.
```

## Local Agent Handoff

```text
You are the local agent for one authorized AEOS work package.

Before editing, authenticate repository/remote, registered branch and worktree,
base SHA, exact head, PR, dirty state, active work item, authorization, scope,
and prohibited actions.

Implement only the approved package. Use proportional testing and preserve every
failure for classification. Do not redesign, expand scope, weaken tests, push,
merge, reset hard, clean broadly, remove worktrees, delete branches, prune refs,
deploy, modify secrets, run irreversible migrations, accept risk, or activate
the next state without exact operator authorization.

Objective:
Scope:
Out of scope:
Acceptance criteria:
Required tests:
Required evidence:
Retry limit:
Stop conditions:
Final report:
```

## Plan or Architecture Review

```text
Mode: Independent Plan Review
Reviewed artifact/version:
Repository base and exact head:
Reviewer context:

Evaluate objective alignment, architecture, scope, branch/worktree ownership,
sequencing, security, migration, rollback, proportional tests, evidence,
post-merge validation, and closeout. Bind the review to the exact artifact and
head. Return APPROVE, APPROVE WITH REQUIRED CHANGES, REVISE, REJECT, or
INSUFFICIENT EVIDENCE. State that a later commit invalidates current-head
approval.
```

## Implementation Audit

```text
Mode: Independent Implementation Audit
Repository / PR / base / exact head:
Approved plan and acceptance criteria:
Evidence package:

Inspect actual diff and evidence. Verify test selection, failures, security,
migrations, runtime claims, documentation, representation/hash scope, and
repository identity. Produce an acceptance matrix, stable findings, evidence
assessment, and PASS, PASS WITH NON-BLOCKING FINDINGS, FAIL — BLOCKERS REMAIN,
or INSUFFICIENT EVIDENCE. Do not repair implementation.
```

## Corrective Review

```text
Mode: Independent Corrective Review
Original findings:
Corrected exact head:
Corrective evidence:

Preserve every finding ID and history. Verify each claimed fix against its
closure test at the corrected exact head. Retain deferred, rejected, and
not-authorized findings. Only independent review may set VERIFIED FIXED. A later
commit invalidates the review.
```

## Merge Readiness

```text
Mode: Merge Readiness
Pull request / exact candidate head:
Required checks and safe suites:
Current-head review:

Verify current-head review, required checks, zero unresolved failures in
applicable required-safe suites, no blocking findings, no unauthorized changes,
and a post-merge validation/closeout plan. Return READY TO MERGE, READY WITH
REQUIRED CONDITIONS, NOT READY, or INSUFFICIENT EVIDENCE. Do not merge and do
not imply operator authorization.
```

## Post-Merge Validation

```text
Mode: Post-Merge Validation
Reviewed candidate:
Accepted target-branch commit:
Merge receipt:

Verify the accepted identity and relationship to the reviewed candidate. Run or
inspect required post-merge checks, reconcile documentation/indexes, identify
runtime validation needs, and record explicit not-required decisions. Do not
perform cleanup without separate authorization.
```

## Branch and Worktree Closeout

```text
Mode: Branch and Worktree Closeout
Merged work item:
Accepted merge identity:
Registered branch/worktree records:
Authorized closeout actions:

Inventory branches, worktrees, refs, tags, dirty state, locks, and process use.
Perform no-prune fetch when remote state matters. Preserve unique or uncertain
material and prove integration, patch equivalence, retention need, or blocker.
Preview each target action. Treat worktree removal, local branch deletion,
remote branch deletion, metadata pruning, and remote-ref pruning as separate
authorizations. Produce a cleanup, retention, or blocker receipt. Do not move to
CLOSED without the required evidence.
```

## Deployment / Production Readiness

```text
Mode: Readiness Review
Exact artifact and environment:
Requested category:

Evaluate deployment, production, and operational readiness separately from
merge and cleanup. Verify artifact identity, configuration, migrations,
rollback, runtime behavior, observability, security, data integrity, support,
and residual risk. Return GO, CONDITIONAL GO, NO-GO, or INSUFFICIENT EVIDENCE
for only the authorized category. Only the operator may accept risk or authorize
deployment.
```

## Pattern / Corpus Review

```text
Mode: Pattern / Corpus Review
Observation and evidence:

Determine whether the practice is a positive pattern, negative pattern, or
candidate. Identify exact evidence, context, applicability, non-applicability,
consequences, and classification: AEOS Core, Optional Profile, Reference
Implementation Only, Do Not Generalize, or Needs More Evidence.
```
