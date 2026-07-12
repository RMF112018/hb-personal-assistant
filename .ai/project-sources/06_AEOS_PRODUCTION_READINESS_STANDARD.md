---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 06 — AEOS Production Readiness Standard

## 1. Purpose

This standard defines how AEOS evaluates readiness for merge, deployment, production operation, and ongoing support. Production readiness is broader than implementation correctness and SHALL be assessed separately.

## 2. Readiness Categories

AEOS distinguishes four categories:

1. Merge readiness.
2. Deployment readiness.
3. Production readiness.
4. Operational readiness.

A GO in one category SHALL NOT imply GO in another.

## 3. Merge Readiness

### Purpose

Determine whether the code may be merged into the target branch.

### Required Evidence

- approved implementation scope;
- passing required tests;
- implementation audit disposition;
- resolved blockers;
- branch state;
- CI status if applicable;
- no unauthorized unrelated changes;
- documentation updated where required.

### Blocking Conditions

- unresolved Critical or High findings;
- failing required tests not accepted as baseline;
- missing evidence for core acceptance criteria;
- unsafe migrations;
- scope drift;
- dirty or ambiguous repository state.

## 4. Deployment Readiness

### Purpose

Determine whether the merged or candidate build may be deployed.

### Required Evidence

- deployable artifact or image identity;
- environment target;
- configuration validation;
- migration plan;
- rollback plan;
- secrets/configuration posture;
- deployment procedure;
- health checks;
- deployment approval.

### Blocking Conditions

- no rollback path;
- unvalidated migration;
- unknown environment configuration;
- missing deployment identity;
- inability to observe service health.

## 5. Production Readiness

### Purpose

Determine whether the feature or change is safe for production use.

### Required Evidence

- runtime validation;
- relevant integration tests;
- data integrity checks;
- security and authorization review;
- performance considerations;
- failure-mode handling;
- observability;
- user-impact assessment;
- residual-risk acceptance.

### Blocking Conditions

- untested production-critical path;
- missing authorization checks;
- data integrity uncertainty;
- no monitoring for failure modes;
- unresolved High/Critical findings;
- unaccepted material risk.

## 6. Operational Readiness

### Purpose

Determine whether the system can be supported after deployment.

### Required Evidence

- monitoring;
- logging;
- alerting or watchpoints;
- runbook updates;
- rollback procedure;
- owner/operator expectations;
- known issue tracking;
- post-deployment validation plan.

## 7. Go / No-Go Decisions

Permitted decisions:

### GO

All applicable gates are satisfied and no blocking issues remain.

### CONDITIONAL GO

Release may proceed only if explicit conditions are satisfied. Conditions SHALL be concrete and verifiable.

### NO-GO

One or more release-blocking issues remain.

### INSUFFICIENT EVIDENCE

The implementation may be correct, but evidence is inadequate to support the requested decision.

## 8. Required Go/No-Go Record

A Go/No-Go record SHALL include:

- decision ID;
- date;
- repository;
- target branch/PR/commit;
- readiness category;
- scope;
- evidence reviewed;
- acceptance-criteria status;
- findings status;
- risk assessment;
- decision;
- conditions if any;
- approver;
- follow-up actions.

## 9. Risk Acceptance

A risk may be accepted only when:

- the risk is identified;
- impact is understood;
- mitigation exists or is intentionally deferred;
- an authorized human accepts it;
- the acceptance is recorded.

AI systems SHALL NOT silently accept risk on behalf of the operator.

## 10. Rollback Requirements

Changes with runtime impact SHOULD include:

- rollback trigger;
- rollback procedure;
- data rollback or forward-fix strategy;
- expected downtime or user impact;
- verification after rollback.

If rollback is impossible or impractical, the record SHALL state the recovery strategy.

## 11. Post-Deployment Validation

A production deployment SHOULD be followed by validation of:

- service health;
- logs;
- core workflows;
- migration success;
- monitoring signals;
- error rates;
- user-facing behavior;
- known watchpoints.

## 12. Common Production Readiness Anti-Patterns

Noncompliant patterns include:

- treating merge readiness as deployment readiness;
- deploying because tests passed;
- skipping rollback analysis;
- omitting runtime validation;
- failing to disclose residual risk;
- accepting unverified migration safety;
- issuing GO with unresolved blockers.
