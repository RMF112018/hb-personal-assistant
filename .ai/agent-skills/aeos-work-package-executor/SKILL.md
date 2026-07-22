---
name: aeos-work-package-executor
description: Execute one explicitly authorized AEOS work package in a registered branch and worktree with surgical changes, proportional validation, preserved failures, representation-aware evidence, and a bounded implementation receipt.
---

## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`. Repository
governance remains authoritative.

# AEOS Work-Package Executor

## Use when

Use only for one authorized implementation work package with approved plan,
work-item ledger, exact repository identity, registered branch/worktree, and
explicit criteria.

## Procedure

### 1. Preflight before editing

Verify repository/remote, branch and worktree registration, base and exact head,
upstream, PR, dirty-state disposition, plan and authorization hashes, work-item
status, prerequisites, scope, and prohibited actions.

Do not absorb unrelated dirty changes or use a different worktree without
reauthorization.

### 2. Inspect before changing

Read relevant implementation, tests, schemas, configuration, governance, and
evidence. State the current behavior and narrow intended correction.

### 3. Establish baseline or prove red

Run the narrowest valid reproduction or baseline test. Preserve exact command,
output, exit code, environment, and head. If the hypothesis cannot be supported,
stop rather than coding speculatively.

### 4. Implement surgically

Modify only approved scope, preserve architecture and safeguards, follow existing
patterns, avoid speculative abstraction, and do not weaken tests, criteria, or
thresholds to obtain a pass.

### 5. Validate proportionally

Apply the repository test-selection standard:

1. direct narrow tests;
2. affected-domain bundle;
3. applicable cross-cutting canaries;
4. applicable lint/type/static checks;
5. broader required-safe suites when policy or risk requires them.

Preserve and classify every failure. A separately authorized corrective stream
must use isolated branch/worktree ownership and non-overlapping scope. Do not
self-authorize a sub-agent to fix unrelated failures.

### 6. Detect deviation and stop

Stop when repository identity drifts, architecture or scope must change, a new
migration or external effect is required, criteria conflict, test infrastructure
is defective, required-safe-suite failures remain unresolved, or retry limits
are reached.

Write a deviation request; do not improvise authority.

### 7. Package evidence

Invoke `aeos-evidence-packager`. Preserve failed and invalid attempts. Bind
evidence to exact head and environment and record representation/hash scope.

### 8. Produce the implementation receipt

Include:

- work item and authorization;
- repository, branch, worktree, base, and exact head;
- prove-red/baseline and prove-green results;
- files and symbols changed;
- proportional tests and failure classifications;
- evidence references;
- deviations and residual risks;
- final repository status;
- recommended audit or checkpoint.

### 9. Stop at the package boundary

Permitted dispositions:

- `IMPLEMENTATION_COMPLETE_PENDING_AUDIT`
- `BLOCKED`
- `FAILED_BOUNDED`
- `INSUFFICIENT_EVIDENCE`
- `OPERATOR_AUTHORIZATION_REQUIRED`

Do not mark the package independently audited, merge it, perform cleanup, or
activate the next package/state unless separately authorized.
