---
name: aeos-finding-reconciler
description: Reconcile an independent AEOS findings ledger into authorized corrective work while preserving finding IDs, history, evidence requirements, rejected/deferred decisions, and re-audit boundaries.
---


## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md` before using this skill. Repository governance remains authoritative.

Do not use this skill when the active goal state or operator authorization does not permit its workflow.

# AEOS Finding Reconciler

## Use when

Use after an independent audit and before or during authorized corrective implementation.

Required:

- original findings ledger;
- audit report;
- operator disposition;
- authorization identifying findings permitted for correction;
- approved scope and repository state.

## Procedure

### 1. Preserve the original ledger

Do not delete, rewrite, merge, or renumber original findings.

Append disposition history with timestamp, actor/context, evidence, and authorization.

### 2. Validate operator decisions

For each finding classify operator treatment:

- `AUTHORIZED_FOR_CORRECTION`
- `DEFERRED_WITH_ACCEPTED_RISK`
- `REJECTED`
- `NEEDS_CLARIFICATION`
- `NOT_AUTHORIZED`

Only the operator may accept risk. An external model recommendation is not risk acceptance.

### 3. Reproduce before correction

For each authorized finding:

- identify expected failing behavior;
- run or define the closure test;
- capture prove-red evidence where reproducible;
- state when the finding cannot be reproduced;
- stop rather than silently substituting a different defect.

### 4. Build corrective work packages

Each package must map to one or more finding IDs and include:

- bounded correction;
- affected files/symbols;
- prohibited collateral changes;
- closure test;
- regression tests;
- evidence;
- retry limit;
- re-audit requirement.

Avoid combining unrelated findings solely for convenience.

### 5. Execute only when separately authorized

Use `aeos-work-package-executor` for code changes. This reconciler does not itself confer implementation authority.

### 6. Update finding history after implementation

Allowed status proposals:

- `CLAIMED_NOT_VERIFIED`
- `OPEN`
- `NOT_REPRODUCIBLE`

The implementation context must not set `VERIFIED_FIXED`. Only independent re-audit may do that.

### 7. Prepare re-audit package

Produce:

```text
corrective-implementation-report.md
finding-reconciliation.yaml
corrective-evidence-index.json
residual-risk.md
reaudit-handoff.md
checkpoint-request.yaml
```

The re-audit handoff must include every original finding, including deferred, rejected, and not-authorized findings.

### 8. Stop

Disposition:

```text
CORRECTIVE_WORK_READY_FOR_REAUDIT
```

or a bounded failure/blocker disposition.

## Integrity rules

- Finding closure requires evidence.
- A changed finding statement creates a new finding; it does not mutate the original.
- Deferred risk remains visible.
- Rejected findings retain rationale and operator identity.
- Corrective success does not imply broader readiness.
