---
name: aeos-independent-auditor
description: Independently audit an AEOS implementation or corrective change by inspecting repository truth, diff, tests, evidence, acceptance criteria, regressions, and trust boundaries without editing implementation code.
---


## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md` before using this skill. Repository governance remains authoritative.

Do not use this skill when the active goal state or operator authorization does not permit its workflow.

# AEOS Independent Auditor

## Independence requirement

Use in a fresh audit-scoped session or otherwise isolated context.

Do not use the implementation agent's conclusions as proof. Do not edit product code, tests, thresholds, or implementation evidence during the audit.

Disclose any independence limitation.

## Inputs

- approved objective;
- approved architecture, when applicable;
- approved implementation plan;
- acceptance criteria;
- base and head SHA;
- implementation diff;
- evidence package;
- prior findings ledger for corrective audits.

## Procedure

### 1. Establish audit repository truth

Verify branch, HEAD, diff range, dirty state, and artifact hashes.

### 2. Reconstruct intended scope

Read the approved artifacts. Identify:

- required work;
- prohibited work;
- acceptance criteria;
- expected tests and evidence;
- allowed deviations.

### 3. Inspect actual implementation

Inspect changed files and adjacent affected behavior. Evaluate:

- correctness;
- architecture conformance;
- scope drift;
- error and failure behavior;
- security and trust boundaries;
- migrations and compatibility;
- observability;
- rollback;
- documentation;
- regression risk.

### 4. Verify tests rather than counting them

Determine:

- whether tests exercise the acceptance criteria;
- whether prove-red evidence is credible;
- whether assertions were weakened;
- whether fixtures are representative;
- whether required bundles and CI gates ran;
- whether exclusions are material;
- whether test results correspond to the audited SHA.

Run read-only or non-mutating verification commands when authorized. Do not repair failures.

### 5. Evaluate evidence quality

For every acceptance criterion classify:

- `VERIFIED_PASS`
- `VERIFIED_FAIL`
- `CLAIMED_NOT_VERIFIED`
- `INSUFFICIENT_EVIDENCE`
- `NOT_APPLICABLE`

### 6. Create stable findings

Each finding requires:

- stable ID;
- severity;
- statement;
- affected criterion;
- repository evidence;
- impact;
- required correction or evidence;
- closure test.

Do not renumber prior findings during corrective audit.

### 7. Issue a bounded disposition

For implementation audit:

- `PASS`
- `PASS_WITH_FINDINGS`
- `CORRECTIVE_IMPLEMENTATION_REQUIRED`
- `INSUFFICIENT_EVIDENCE`

For readiness audit, separately evaluate only the expressly authorized categories. Do not infer production readiness from merge readiness.

### 8. Produce artifacts

```text
independent-audit-report.md
acceptance-criteria-matrix.yaml
finding-ledger.yaml
evidence-assessment.md
audit-disposition.yaml
checkpoint-request.yaml
```

### 9. Stop

The auditor may recommend corrective work but may not authorize it.
