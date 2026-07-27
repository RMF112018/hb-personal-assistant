---
name: aeos-finding-reconciler
description: Reconcile an independent AEOS findings ledger into separately authorized corrective work while preserving finding identity and history, binding closure evidence to the corrected exact head, and retaining re-audit and risk boundaries.
---

## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`. Repository
governance remains authoritative.

# AEOS Finding Reconciler

## Use when

Use after an independent audit and before or during separately authorized
corrective implementation.

Required inputs:

- original findings ledger and audit report;
- exact audited head and corrected candidate identity;
- operator disposition and authorization;
- findings permitted for correction;
- approved scope, branch, worktree, tests, and evidence requirements.

## Procedure

### 1. Preserve the original ledger

Do not delete, rewrite, merge, or renumber findings. Append history with
timestamp, actor/context, authorization, repository head, and evidence.

### 2. Validate operator treatment

For each finding classify:

- `AUTHORIZED_FOR_CORRECTION`
- `DEFERRED_WITH_ACCEPTED_RISK`
- `REJECTED`
- `NEEDS_CLARIFICATION`
- `NOT_AUTHORIZED`

Only the operator may accept risk. A reviewer recommendation or publication is
not risk acceptance.

### 3. Authenticate corrective identity

Verify the corrective branch and worktree are registered, authorization binds
the permitted finding IDs and expected head, unrelated scope is excluded, and
any parallel corrective stream is separately authorized and non-overlapping.

### 4. Reproduce before correction

For each authorized finding, identify expected failure and closure test, capture
prove-red or baseline evidence when reproducible, and stop rather than silently
substituting a different defect.

### 5. Build corrective work packages

Each package maps to one or more finding IDs and includes bounded correction,
files/symbols, prohibited collateral change, proportional tests, closure test,
evidence representation/hash scope, retry limit, and independent re-audit.

### 6. Execute only under separate authorization

Use `aeos-work-package-executor` for code changes. This reconciler does not
confer implementation authority or authorize unrelated-failure correction.

### 7. Update finding history after implementation

The implementation context may propose:

- `FIX CLAIMED`
- `OPEN`
- `NOT REPRODUCIBLE`

It SHALL NOT set `VERIFIED FIXED`. Only independent re-audit at the corrected
exact head may do that.

A later commit after re-audit invalidates current-head closure verification.

### 8. Prepare the re-audit package

```text
corrective-implementation-report.md
corrected-identity.yaml
finding-reconciliation.yaml
corrective-evidence-index.json
residual-risk.md
reaudit-handoff.md
checkpoint-request.yaml
```

Include every original finding, including deferred, rejected, and not-authorized
items. Bind each claim and closure test to the corrected exact head.

### 9. Stop

Return `CORRECTIVE_WORK_READY_FOR_REAUDIT` or a bounded blocker/failure
disposition. Do not self-verify, merge, perform cleanup, accept risk, or activate
the next state.

## Integrity rules

- Finding closure requires independent evidence at the exact corrected head.
- A changed finding statement creates a new finding rather than mutating the
  original.
- Deferred risk remains visible with operator identity.
- Rejected findings retain rationale.
- Corrective success does not imply merge, cleanup, deployment, or production
  readiness.
