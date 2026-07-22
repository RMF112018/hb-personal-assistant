---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 06 — AEOS Production Readiness Standard

## 1. Purpose

This standard separates readiness for merge, post-merge closure, deployment,
production use, and ongoing operation. A positive decision in one category does
not imply a positive decision in another.

## 2. Readiness Categories

1. Merge readiness.
2. Post-merge validation and cleanup/closure readiness.
3. Deployment readiness.
4. Production readiness.
5. Operational readiness.

## 3. Merge Readiness

Required evidence:

- approved scope and exact candidate head;
- current-head independent review or audit;
- required checks and proportional test evidence;
- zero unresolved failures in applicable required-safe suites;
- resolved blocking findings;
- no unauthorized unrelated changes;
- clean or explicitly governed repository state;
- documentation and closeout plan.

Blocking conditions include stale review, unresolved required-safe-suite
failures, blocking findings, ambiguous identity, unsafe migration, scope drift,
or missing core evidence.

Merge readiness does not authorize merge.

## 4. Merge Authorization

Only the operator may authorize merge. Authorization SHALL identify the exact
pull request and head and any required method or conditions.

A merge transitions work to `MERGED_PENDING_CLEANUP`. It does not authorize
cleanup, deployment, production activation, or closure.

## 5. Post-Merge Validation and Closure Readiness

Required evidence:

- accepted target-branch commit;
- relationship to the reviewed candidate;
- applicable post-merge checks or tests;
- documentation/index reconciliation;
- explicit not-required decisions where validation is omitted;
- inventory and preservation evidence;
- branch/worktree integration or retention proof;
- cleanup, retention, or blocker receipt.

Closure is blocked by unknown dirty state, unique unpreserved work, unverified
integration, ambiguous worktree/branch/ref disposition, or unauthorized
cleanup.

## 6. Deployment Readiness

Required evidence:

- deployable artifact or image identity;
- target environment;
- configuration and secret posture;
- migration and rollback plan;
- deployment procedure and authorization;
- health checks and observability;
- dependency and compatibility validation.

A merged or closed change is not automatically deployable.

## 7. Production Readiness

Required evidence:

- runtime validation of production-critical behavior;
- relevant integration and failure-mode tests;
- data-integrity and security checks;
- performance and capacity considerations;
- observability and user-impact assessment;
- rollback or forward-fix strategy;
- residual-risk disposition by the operator.

Blocking conditions include untested critical paths, missing authorization
checks, data-integrity uncertainty, unresolved High/Critical findings,
unobservable failure modes, or unaccepted material risk.

## 8. Operational Readiness

Required evidence:

- monitoring, logging, and alerting;
- runbooks and ownership;
- rollback or recovery procedures;
- known-issue tracking;
- watchpoints and post-deployment validation;
- support expectations and escalation path.

## 9. Decisions

For deployment, production, or operational readiness:

- `GO`
- `CONDITIONAL GO`
- `NO-GO`
- `INSUFFICIENT EVIDENCE`

For merge readiness:

- `READY TO MERGE`
- `READY WITH REQUIRED CONDITIONS`
- `NOT READY`
- `INSUFFICIENT EVIDENCE`

Every decision SHALL identify scope, exact identity, evidence, blockers,
conditions, approver, residual risk, and follow-up.

## 10. Risk Acceptance

Only an authorized human may accept risk. The record SHALL identify the risk,
impact, mitigation or deferral, scope, duration when applicable, approver, and
timestamp.

AI systems SHALL NOT infer risk acceptance from merge, publication, review, or
tool access.

## 11. Readiness Anti-Patterns

Noncompliant behavior includes:

- treating mergeability as merge readiness;
- treating merge readiness as merge authorization;
- treating merge as cleanup, deployment, or closure;
- treating cleanup as deployment readiness;
- issuing GO from unit tests alone;
- omitting rollback or runtime validation;
- accepting unresolved failures without evidence and authority;
- combining readiness categories into one ambiguous disposition.
