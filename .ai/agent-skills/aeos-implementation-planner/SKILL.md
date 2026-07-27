---
name: aeos-implementation-planner
description: Create an executable AEOS implementation plan from approved repository truth and architecture with exact branch/worktree identity, proportional tests, representation-aware evidence, rollback, and post-merge closeout requirements.
---

## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`. Repository
governance remains authoritative.

# AEOS Implementation Planner

## Use when

Use only when repository truth and acceptance criteria are approved, required
architecture is approved or formally not required, the state is
`IMPLEMENTATION_PLANNING`, and valid authorization permits planning. Do not edit
product code.

## Procedure

### 1. Revalidate inputs and identity

Verify approved artifacts by path, version, representation, and hash. Confirm
repository, branch, registered worktree, base, exact head, PR, and authorization
have not drifted.

### 2. Restate the bounded objective

Document objective, scope, out-of-scope, constraints, criteria, unresolved
decisions, consequential actions, and operator-only decisions. Do not silently
resolve architecture during planning.

### 3. Define execution ownership

Record:

- branch identity and owner;
- worktree identity/path and owner;
- base and expected head;
- issue, goal, and work item;
- expected PR relationship;
- expected post-merge branch/worktree disposition.

### 4. Map implementation surfaces

Identify expected modules, symbols, tests, schemas, migrations, configuration,
CI, documentation, evidence, and runtime/operational validation. Label uncertain
surfaces as expected rather than guaranteed.

### 5. Decompose work packages

Each package includes ID, objective, prerequisites, exact scope, out-of-scope,
expected files/symbols, criteria, authorization boundary, tests, evidence,
representation/hash requirements, rollback, retry limit, stop conditions,
review checkpoint, and expected closeout disposition.

Prefer independently verifiable packages and isolate shared infrastructure from
unrelated feature work.

### 6. Define proportional testing

Apply `.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md`. Map changed
risk surfaces to inner-loop, candidate, checkpoint, canary, and merge/release
suites. Define classification for every failure and zero-unresolved-failure
requirements for applicable required-safe suites.

Separate corrective streams require separate authorization, isolated
branch/worktree ownership, non-overlap, evidence, and independent review.

### 7. Define evidence

Specify exact commands, exit codes, outputs, CI, tests, metrics, migration or
runtime receipts, before/after state, representation, MIME type, hash scope,
hashes, limitations, and environment attestation.

### 8. Define rollback, recovery, and closeout

Address code rollback, data/schema compatibility, interrupted commands,
generated files, external effects, post-merge validation, no-prune inventory,
preservation, integration proof, and cleanup/retention/blocker receipts.

### 9. Produce artifacts

```text
implementation-plan.md
work-item-ledger.yaml
acceptance-traceability.yaml
test-plan.md
evidence-plan.md
rollback-plan.md
post-merge-closeout-plan.md
checkpoint-request.yaml
```

### 10. Stop for independent review

Return `READY_FOR_EXTERNAL_REVIEW`. Do not begin implementation or activate the
next state.

## Plan quality gate

A plan is not executable without authoritative identity, bounded scope,
branch/worktree ownership, package sequencing, acceptance traceability,
proportional tests, evidence representation, rollback/recovery, stop conditions,
final-report contract, and expected post-merge closeout.
