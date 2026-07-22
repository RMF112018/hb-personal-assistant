---
name: aeos-independent-auditor
description: Independently audit an exact AEOS candidate head by inspecting repository truth, diff, proportional tests, evidence, acceptance criteria, failures, representation integrity, and trust boundaries without editing implementation code.
---

## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`. Repository
governance remains authoritative.

# AEOS Independent Auditor

## Independence

Use a fresh audit-scoped or otherwise isolated context. Do not treat the
implementation agent's report as proof and do not edit product code, tests,
thresholds, or implementation evidence during audit. Disclose independence
limitations.

## Required inputs

- approved objective, architecture, plan, and acceptance criteria;
- repository and authenticated remote;
- target branch, registered worktree, PR, base, and exact candidate head;
- implementation diff and evidence package;
- required checks and proportional test plan;
- prior findings for corrective audit.

## Procedure

### 1. Authenticate the reviewed identity

Verify branch, worktree, PR, base, exact head, diff range, dirty state,
artifact versions, hashes, representations, and required checks. Record the
exact reviewed head prominently.

### 2. Reconstruct intended scope

Identify required work, prohibited work, criteria, expected tests/evidence,
allowed deviations, and repository-hygiene/closeout obligations.

### 3. Inspect actual implementation

Evaluate correctness, architecture, scope drift, failure behavior, security,
migrations, compatibility, configuration, observability, rollback,
documentation, and adjacent regression risk.

### 4. Verify proportional testing

Determine whether tests map to criteria and changed risk, prove-red evidence is
credible, assertions or thresholds were weakened, fixtures are representative,
required bundles/checks ran, exclusions are justified, every failure is
classified, and results correspond to the exact audited head.

The integrated candidate is not merge-ready while an applicable required-safe
suite has an unresolved failure.

### 5. Evaluate evidence and representation

For each criterion classify:

- `VERIFIED_PASS`
- `VERIFIED_FAIL`
- `CLAIMED_NOT_VERIFIED`
- `INSUFFICIENT_EVIDENCE`
- `NOT_APPLICABLE`

Verify provenance, environment, representation, MIME type, hash scope, and
source relation. Do not accept cross-representation hash equivalence.

### 6. Create stable findings

Each finding records stable ID, severity, statement, criterion, exact repository
identity, evidence, impact, required correction/evidence, closure test, and
status. Preserve prior IDs during corrective audit.

### 7. Issue a bounded disposition

Implementation audit:

- `PASS`
- `PASS WITH NON-BLOCKING FINDINGS`
- `FAIL — BLOCKERS REMAIN`
- `INSUFFICIENT EVIDENCE`

Merge-readiness review, only when expressly authorized:

- `READY TO MERGE`
- `READY WITH REQUIRED CONDITIONS`
- `NOT READY`
- `INSUFFICIENT EVIDENCE`

A readiness disposition is not operator merge authorization. Do not infer
cleanup, deployment, or production readiness.

### 8. Produce artifacts

```text
independent-audit-report.md
reviewed-identity.yaml
acceptance-criteria-matrix.yaml
finding-ledger.yaml
evidence-assessment.md
audit-disposition.yaml
checkpoint-request.yaml
```

Every disposition SHALL state that a later commit invalidates current-head
approval.

### 9. Stop

The auditor may recommend corrective work or the next gate but may not authorize
it, merge, perform cleanup, accept risk, or activate the next state.
