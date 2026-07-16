---
name: aeos-repository-truth
description: Perform an AEOS repository-truth investigation without designing or implementing, producing verified facts, evidence, assumptions, unknowns, and a gap matrix.
---


## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md` before using this skill. Repository governance remains authoritative.

Do not use this skill when the active goal state or operator authorization does not permit its workflow.

# AEOS Repository Truth

## Use when

Use only for discovery, evidence reconstruction, baseline establishment, or re-verification.

This is a read-only workflow unless the operator explicitly authorizes writing the resulting governance artifacts. Do not modify product code, tests, migrations, CI, or runtime configuration.

## Required questions

Establish:

- What repository, branch, worktree, and commit are under review?
- What governance applies?
- What approved objective and acceptance criteria apply?
- What implementation, tests, schemas, migrations, CI, runtime surfaces, and evidence exist?
- Which prior claims are verified, unverified, contradicted, stale, or unavailable?
- What gaps remain?
- What next gate is justified?

## Procedure

### 1. Preflight

Capture repository identity and dirty state. Identify local worktrees and relevant branch relationships when material.

### 2. Read governing sources

Read the Master Index and only the AEOS sources applicable to the discovery workflow. Read repository-local specifications and ADRs relevant to the objective.

### 3. Build an investigation map

List:

- implementation components;
- tests and test bundles;
- schemas and migrations;
- configuration;
- CLI/API/MCP surfaces;
- CI workflows;
- evidence bundles;
- runtime or operational surfaces;
- deployment artifacts, only if in scope.

### 4. Inspect high-authority evidence

Use this order:

1. current implementation;
2. current tests;
3. schemas and migrations;
4. configuration;
5. CI definitions;
6. runtime output;
7. committed evidence;
8. approved specifications;
9. summaries and prior reports.

Do not repeat a prior audit merely to create more prose. Reverify material claims and identify changed evidence.

### 5. Classify every material statement

Use the shared claim taxonomy:

- `VERIFIED`
- `CLAIMED_NOT_VERIFIED`
- `ASSUMED`
- `UNKNOWN`
- `UNAVAILABLE`
- `NOT_APPLICABLE`

### 6. Trace gaps to requirements

For each acceptance criterion record:

- criterion identifier;
- applicable evidence;
- current implementation status;
- test status;
- evidence strength;
- gap;
- risk;
- next required action.

### 7. Produce checkpoint artifacts

Create:

```text
repository-truth-report.md
evidence-index.json
verified-facts.yaml
assumptions-and-unknowns.md
gap-matrix.yaml
checkpoint-request.yaml
```

Use `.ai/aeos/goals/<goal-id>/` unless the approved goal specifies another governed location.

### 8. Stop

Disposition:

```text
READY_FOR_EXTERNAL_REVIEW
```

Recommend an architecture or planning gate only when repository truth supports it. Do not begin that work.

## Required report sections

1. Scope and authority
2. Repository state
3. Evidence-access limitations
4. System/component map
5. Verified facts
6. Claims not verified
7. Assumptions and unknowns
8. Acceptance-criteria gap matrix
9. Risks and contradictions
10. Recommended next gate
11. Bounded disposition
