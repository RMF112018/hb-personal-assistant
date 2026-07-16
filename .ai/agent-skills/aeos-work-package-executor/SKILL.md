---
name: aeos-work-package-executor
description: Execute one explicitly authorized AEOS implementation work package with surgical changes, prove-red/prove-green validation, evidence capture, deviation stops, and a bounded implementation receipt.
---


## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md` before using this skill. Repository governance remains authoritative.

Do not use this skill when the active goal state or operator authorization does not permit its workflow.

# AEOS Work-Package Executor

## Use when

Use only for one authorized implementation work package.

Required:

- approved implementation plan;
- approved work-item ledger;
- valid operator authorization;
- expected branch and HEAD;
- exact work-package identifier;
- explicit scope and acceptance criteria.

## Procedure

### 1. Preflight before editing

Capture repository state. Verify:

- branch and HEAD;
- dirty-tree disposition;
- plan and authorization hashes;
- work package is `AUTHORIZED`;
- prerequisites are satisfied;
- scope and prohibitions are understood.

Do not absorb unrelated dirty changes into the package.

### 2. Inspect before changing

Read the relevant implementation, tests, schemas, configuration, and evidence. State the current behavior and planned narrow correction.

### 3. Establish baseline or prove red

Run the narrowest valid reproduction or baseline test. Save exact output and exit code.

If reproduction is impossible, stop and report rather than coding against an unsupported hypothesis.

### 4. Implement surgically

- modify only approved scope;
- preserve architecture;
- follow existing patterns;
- avoid speculative abstraction;
- do not delete unrelated code;
- do not weaken tests or thresholds;
- do not change accepted requirements to obtain a pass.

### 5. Validate in layers

Run:

1. direct narrow tests;
2. affected-domain bundle;
3. cross-cutting canaries when applicable;
4. lint/type checks applicable to changed modules;
5. broader regression only when required by the plan.

Record exclusions and why they are safe.

### 6. Detect deviation

Stop before proceeding when:

- expected implementation differs materially;
- architecture must change;
- new migration or external side effect is required;
- scope expands;
- acceptance criteria conflict;
- test infrastructure is defective;
- retry limit is reached.

Write a deviation request; do not improvise authorization.

### 7. Package evidence

Invoke `aeos-evidence-packager`. Preserve failed attempts and final evidence.

### 8. Produce implementation receipt

Include the shared final-report contract plus:

- work-package disposition;
- prove-red result;
- prove-green result;
- files and symbols changed;
- tests and exact outcomes;
- residual risks;
- recommended next work package or gate.

### 9. Stop at the package boundary

Permitted dispositions:

- `IMPLEMENTATION_COMPLETE_PENDING_AUDIT`
- `BLOCKED`
- `FAILED_BOUNDED`
- `INSUFFICIENT_EVIDENCE`
- `OPERATOR_AUTHORIZATION_REQUIRED`

Do not mark the package independently audited. Do not activate the next package unless the approved plan and authorization explicitly permit controlled continuation.
