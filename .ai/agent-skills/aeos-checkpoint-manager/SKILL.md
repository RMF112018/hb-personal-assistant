---
name: aeos-checkpoint-manager
description: Validate and close one AEOS workflow checkpoint, bind artifacts and evidence to exact repository identity, prevent unauthorized state advancement, and require post-merge validation and closeout receipts before closure.
---

## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`. Repository
governance remains authoritative.

# AEOS Checkpoint Manager

## Use when

Use at the end of every governed state and before external review, operator
decision, merge, or closeout. This skill records a bounded checkpoint; it does
not approve or activate the next state.

## Inputs

- active goal, state, work item, and authorization;
- expected and completed artifacts;
- acceptance criteria;
- exact repository and environment identity;
- evidence index;
- deviations, failures, and unresolved findings;
- requested next state;
- merge or closeout receipts when applicable.

## Procedure

### 1. Verify identity

Confirm goal, state, work item, authorization, branch, worktree, base, exact
head, PR, and checkpoint agree. Treat a later commit as repository drift.

### 2. Validate artifacts

For every expected artifact verify existence, nonempty content, identifiers,
references, schema, representation, hash scope, and absence of sensitive data.
Do not overwrite closed evidence or failed runs.

### 3. Validate claims and tests

Map every claim and acceptance criterion to evidence. Preserve all failures and
their classifications. Mark unsupported claims `CLAIMED_NOT_VERIFIED` and list
unavailable evidence. Reject circular summary-only evidence.

### 4. Capture repository state

Record branch, worktree identity, base and exact head, upstream, PR/checks,
dirty/untracked state, and diff summary.

### 5. Build the artifact manifest

For raw files or repository blobs, record path, type, representation, size,
hash scope, and SHA-256. For native objects, record stable identity and use
`hash_scope: not_applicable` unless a separately identified export/source is
hashed.

### 6. Enforce lifecycle rules

Ordinary stage completion may move:

```text
IN_PROGRESS → READY_FOR_REVIEW
```

The checkpoint SHALL NOT activate the requested next state.

Merge SHALL record:

```text
MERGE_AUTHORIZATION → MERGED_PENDING_CLEANUP
```

`MERGED_PENDING_CLEANUP` SHALL NOT move directly to `CLOSED`.

Before closure verify:

- accepted merge identity;
- post-merge validation or explicit not-required decision;
- preservation and integration proof;
- worktree, local branch, remote branch, metadata, and ref disposition;
- cleanup, retention, or blocker receipt;
- operator-authorized closure transition.

### 7. Write the checkpoint request

Include current lifecycle/state status, exact repository identity, artifact
manifest, verified and unverified claims, test failures, deviations, findings,
requested next state, operator action required, and closeout status.

### 8. Produce the handoff and stop

Provide exact review objective, artifacts, diff, criteria, evidence, limitations,
and disposition vocabulary. State:

```text
No further workflow state is authorized.
```

## Failure behavior

When artifacts, identity, evidence, tests, authorization, or closeout receipts
are incomplete or contradictory, preserve state and return `BLOCKED`,
`INSUFFICIENT_EVIDENCE`, or `OPERATOR_AUTHORIZATION_REQUIRED`.
