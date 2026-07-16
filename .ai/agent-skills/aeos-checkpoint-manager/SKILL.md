---
name: aeos-checkpoint-manager
description: Validate and close an AEOS workflow checkpoint, hash artifacts, record repository state and unresolved claims, request external review, and prevent automatic next-state activation.
---


## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md` before using this skill. Repository governance remains authoritative.

Do not use this skill when the active goal state or operator authorization does not permit its workflow.

# AEOS Checkpoint Manager

## Use when

Use at the end of every governed workflow stage and before handing work to an external reviewer or operator.

This skill closes a state. It never approves or activates the next state.

## Inputs

- active goal and state;
- expected-artifact list;
- completed artifacts;
- acceptance criteria;
- repository state;
- deviations and unresolved findings;
- requested next state.

## Procedure

### 1. Verify stage identity

Confirm the active goal, state, authorization, work item, and expected checkpoint agree across the goal artifacts.

### 2. Validate artifact completeness

For every expected artifact:

- verify it exists;
- verify it is nonempty;
- verify identifiers agree;
- verify references resolve;
- verify required sections or schema fields exist;
- verify no prior closed evidence was overwritten;
- verify sensitive data is absent.

### 3. Validate evidence claims

For every claimed result:

- identify supporting evidence;
- classify evidence strength;
- mark unsupported claims as `CLAIMED_NOT_VERIFIED`;
- list unavailable evidence;
- reject circular evidence where an agent summary cites only another summary.

### 4. Capture repository state

Record:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --stat
```

Capture base and current SHA. Record dirty state accurately.

### 5. Hash artifacts

Calculate SHA-256 for each checkpoint artifact. Include path, type, size, and hash in `artifact-manifest.json`.

### 6. Write the checkpoint request

Use the shared template and schema. Include:

- current state;
- bounded disposition;
- repository identity;
- artifact manifest;
- verified and unverified claims;
- deviations;
- unresolved findings;
- requested next state;
- operator action required.

### 7. Update state without advancing it

Permitted state change:

```text
IN_PROGRESS → READY_FOR_REVIEW
```

Not permitted:

```text
READY_FOR_REVIEW → next active state
```

Only a later validated operator authorization may activate the next state.

### 8. Produce external-review handoff

Include:

- exact review objective;
- governing artifacts;
- files and diff to inspect;
- acceptance criteria;
- evidence index;
- known limitations;
- required review disposition vocabulary.

### 9. Stop

Output exactly one bounded terminal disposition and explicitly state:

```text
No further workflow state is authorized.
```

## Failure behavior

If artifacts are incomplete or contradictory:

- do not fabricate missing evidence;
- produce a checkpoint defect list;
- return `BLOCKED` or `INSUFFICIENT_EVIDENCE`;
- leave the current state active or blocked according to the approved state model.
