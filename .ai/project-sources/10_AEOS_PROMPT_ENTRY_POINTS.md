---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 10 — AEOS Prompt Entry Points

## 1. Purpose

This document provides concise prompt templates for initiating AEOS workflow modes. These prompts are entry points, not replacements for the governing standards.

## 2. Discovery Prompt

```text
Mode: Discovery / Repository Truth

Target repository:
Target branch/PR/commit:
Objective:

Use AEOS. First establish repository truth. Identify current branch, HEAD SHA, relevant files, tests, runtime surfaces, known constraints, verified facts, assumptions, unknowns, and evidence gaps. Do not design or implement yet. Produce a repository-truth report and recommend the next gate.
```

## 3. Architecture Prompt

```text
Mode: Architecture

Target repository:
Approved objective:
Repository-truth report:
Constraints:

Use AEOS. Develop the architecture for this objective. Preserve repository truth and constraints. Include affected components, interfaces, data model, trust boundaries, failure behavior, observability, alternatives considered, rejected alternatives, invariants, risks, and acceptance criteria. Do not generate an implementation prompt until the architecture is complete.
```

## 4. Implementation Planning Prompt

```text
Mode: Implementation Planning

Target repository:
Approved architecture:
Acceptance criteria:
Constraints:

Use AEOS. Produce an executable implementation plan for a local coding agent. Include repo preflight, scope, out-of-scope, phases, expected files, tests, evidence requirements, rollback strategy, forbidden actions, stop conditions, and required final report format.
```

## 5. Local Agent Handoff Prompt

```text
You are the local coding agent for an AEOS-governed implementation.

Before editing, report repository path, branch, HEAD SHA, dirty state, and relevant files inspected.

Implement only the approved scope below. Do not redesign architecture, expand scope, push, merge, force-push, reset hard, delete files outside scope, deploy, modify secrets, or run irreversible migrations without explicit approval.

Objective:
Approved architecture:
Scope:
Out of scope:
Acceptance criteria:
Implementation phases:
Required tests:
Required evidence:
Stop conditions:
Final report format:
```

## 6. Plan Review Prompt

```text
Mode: Plan Review

Review the local agent's implementation plan under AEOS. Compare it against the approved objective, architecture, constraints, and acceptance criteria. Identify design drift, missing work, unsafe sequencing, migration risk, test gaps, evidence gaps, and scope expansion.

Return one disposition: APPROVE, APPROVE WITH REQUIRED CHANGES, REVISE BEFORE IMPLEMENTATION, or REJECT.
```

## 7. Implementation Audit Prompt

```text
Mode: Implementation Audit

Conduct an AEOS implementation audit. Do not rely on the implementation summary as proof. Inspect the actual diff, changed files, tests, evidence, acceptance criteria, regression risk, security/trust boundaries, migrations, runtime validation, and documentation. Produce an acceptance-criteria matrix, findings ledger, evidence assessment, and audit disposition.
```

## 8. Corrective Review Prompt

```text
Mode: Corrective Review

Review the corrective work against the existing finding ledger. Preserve original finding IDs. For each finding, determine whether the fix is verified, claimed but not verified, still open, deferred with accepted risk, rejected, or not reproducible. Require evidence for closure.
```

## 9. Production Readiness Prompt

```text
Mode: Production Readiness

Evaluate merge readiness, deployment readiness, production readiness, and operational readiness separately. Use AEOS evidence and trust standards. Identify blockers, accepted risks, rollback readiness, observability, migration safety, and post-deployment validation. Do not issue GO unless evidence supports it.
```

## 10. Go / No-Go Prompt

```text
Mode: Go / No-Go

Issue a bounded AEOS Go/No-Go decision for:
- Merge readiness:
- Deployment readiness:
- Production readiness:
- Operational readiness:

Use only verified evidence. Return GO, CONDITIONAL GO, NO-GO, or INSUFFICIENT EVIDENCE. Include evidence reviewed, unresolved findings, accepted risks, required conditions, and follow-up actions.
```

## 11. Corpus Promotion Prompt

```text
Mode: Pattern / Corpus Review

Evaluate whether this observed engineering practice should be promoted into the AEOS corpus. Identify evidence, pattern category, applicability, non-applicability, consequences, and generalization classification: AEOS Core, Optional Profile, Reference Implementation Only, Do Not Generalize, or Needs More Evidence.
```
