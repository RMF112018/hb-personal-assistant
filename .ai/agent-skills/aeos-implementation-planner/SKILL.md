---
name: aeos-implementation-planner
description: Create an executable AEOS implementation plan from approved repository truth and architecture, with work packages, acceptance traceability, tests, evidence, rollback, prohibitions, and stop conditions.
---


## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md` before using this skill. Repository governance remains authoritative.

Do not use this skill when the active goal state or operator authorization does not permit its workflow.

# AEOS Implementation Planner

## Use when

Use only when:

- repository truth is approved;
- required architecture is approved or formally not required;
- acceptance criteria are approved;
- the active state is `IMPLEMENTATION_PLANNING`;
- a valid authorization permits planning.

Do not edit product code.

## Procedure

### 1. Revalidate inputs

Verify approved artifacts by path and hash. Confirm repository HEAD has not drifted from the planning authorization.

### 2. Restate the bounded objective

Document:

- approved objective;
- scope;
- out of scope;
- governing constraints;
- acceptance criteria;
- unresolved decisions;
- consequential actions.

Do not silently resolve architecture decisions during implementation planning.

### 3. Map implementation surfaces

Identify expected:

- modules and symbols;
- tests;
- schemas and migrations;
- configurations;
- CI workflows;
- documentation;
- evidence locations;
- runtime or operational validation.

Label uncertain surfaces as expected, not guaranteed.

### 4. Define prove-red strategy

For each defect or missing invariant, define how failure will be demonstrated before correction, when reproducible.

Do not require artificial failing tests for pure scaffolding where no prior behavior exists; state the appropriate baseline proof instead.

### 5. Decompose work packages

Each package must include:

- identifier;
- objective;
- prerequisites;
- exact scope;
- out of scope;
- expected files/symbols;
- acceptance criteria;
- required tests;
- required evidence;
- rollback;
- retry limit;
- stop conditions;
- review checkpoint.

Prefer independently verifiable packages. Separate harness changes from production-code changes when practical.

### 6. Select validation routes

Account for repository-specific test bundles, opt-in integration/live markers, partial lint/type coverage, and CI requirements.

Never infer that a general green command covers excluded modules or unlisted tests.

### 7. Define evidence

Specify:

- commands and exit codes;
- test reports;
- benchmark or migration receipts;
- before/after state;
- hashes;
- logs;
- limitations;
- required environment attestation.

### 8. Define rollback and recovery

Address:

- code rollback;
- data/schema compatibility;
- partially completed work;
- interrupted commands;
- generated fixtures;
- external side effects.

### 9. Define forbidden actions and stops

Include repository prohibitions plus objective-specific restrictions.

### 10. Produce artifacts

Create:

```text
implementation-plan.md
work-item-ledger.yaml
acceptance-traceability.yaml
test-plan.md
evidence-plan.md
rollback-plan.md
checkpoint-request.yaml
```

### 11. Stop for independent plan review

Disposition:

```text
READY_FOR_EXTERNAL_REVIEW
```

Do not begin implementation.

## Plan quality gate

A plan is not executable if it lacks any of:

- authoritative baseline;
- bounded scope;
- work-package sequencing;
- acceptance traceability;
- test strategy;
- evidence contract;
- rollback/recovery;
- stop conditions;
- final-report contract.
