---
name: aeos-repository-truth
description: Perform a read-only AEOS repository-truth investigation with exact branch, worktree, ref, test, runtime, and evidence identity, producing verified facts, unknowns, and a bounded gap matrix without pruning or implementation.
---

## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`. Repository
governance remains authoritative.

# AEOS Repository Truth

## Use when

Use for discovery, baseline establishment, evidence reconstruction, hygiene
inventory, or re-verification. This workflow is read-only unless publication of
its artifacts is separately authorized.

## Required questions

- What repository, authenticated remote, branch, worktree, base, and exact head
  are under review?
- What issue, goal, work item, authorization, PR, checks, and review state apply?
- What implementation, tests, schemas, migrations, CI, runtime, and evidence
  exist?
- Which prior claims are verified, stale, contradicted, unknown, or unavailable?
- What branch/worktree/ref state is relevant to preservation or closeout?
- What next gate is justified?

## Procedure

### 1. Authenticate repository state

Capture repository path, remote, default branch, current branch, upstream, base
and exact head, merge base, PR/checks, dirty/untracked state, and registered
branch/worktree identities.

### 2. Inventory without pruning

When repository hygiene or closeout is material, inventory:

- local and remote branches;
- worktrees and administrative metadata;
- refs and tags;
- dirty and untracked material;
- locks, storage constraints, and process dependencies;
- integration, patch-equivalence, and divergence relationships.

Perform no-prune fetch when remote truth is required. Do not delete, remove,
repair, or prune during repository truth. Absence from a partial inventory is
not proof of absence.

### 3. Read governing sources

Read only the applicable repository and AEOS sources, including ADR-019,
`POL-GIT-HYGIENE-001`, and the repository test-selection standard when
applicable.

### 4. Build an investigation map

Map implementation, tests and bundles, schemas and migrations, configuration,
CLI/API/MCP surfaces, CI, evidence, runtime, deployment artifacts when in scope,
and historical claims.

### 5. Inspect high-authority evidence

Prefer authenticated repository and runtime evidence over specifications,
reports, summaries, and memory. Reverify material claims rather than repeating
prior narrative.

### 6. Classify claims

Use:

- `VERIFIED`
- `CLAIMED_NOT_VERIFIED`
- `ASSUMED`
- `UNKNOWN`
- `UNAVAILABLE`
- `NOT_APPLICABLE`

For every acceptance criterion record implementation status, test status,
evidence strength, gap, risk, and next action.

### 7. Produce artifacts

```text
repository-truth-report.md
repository-identity.yaml
branch-worktree-ref-inventory.yaml   # when applicable
evidence-index.json
verified-facts.yaml
assumptions-and-unknowns.md
gap-matrix.yaml
checkpoint-request.yaml
```

Use the approved goal location. Evidence entries must identify representation
and hash scope when material.

### 8. Stop

Return `READY_FOR_EXTERNAL_REVIEW`, `BLOCKED`, or `INSUFFICIENT_EVIDENCE`.
Recommend but do not begin architecture, implementation, cleanup, or the next
state.

## Required report sections

1. Scope, authority, and exact identity.
2. Evidence-access limitations.
3. Repository and runtime map.
4. Branch/worktree/ref inventory when applicable.
5. Verified facts and contradicted claims.
6. Claims not verified, assumptions, unknowns, and unavailable evidence.
7. Acceptance-criteria gap matrix.
8. Preservation or cleanup blockers.
9. Risks and recommended next gate.
10. Bounded disposition.
