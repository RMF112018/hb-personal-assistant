---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 09 — AEOS Pattern Language

## 1. Purpose

This standard defines how AEOS records, evaluates, and promotes engineering patterns. Patterns are not invented preferences. They are evidence-derived solutions or anti-patterns observed in real engineering work.

## 2. Pattern Categories

### Positive Pattern

A repeatable engineering approach that improved reliability, auditability, safety, maintainability, or delivery quality.

### Negative Pattern

A recurring failure mode, unsafe shortcut, or misleading practice that should be avoided or guarded against.

### Candidate Pattern

An observed practice that may become a pattern but requires more evidence.

## 3. Pattern Promotion Pipeline

A pattern SHOULD follow this pipeline:

```text
Observation
→ Evidence
→ Candidate Pattern
→ Review
→ Classification
→ Pattern Entry
→ Adoption or Rejection
```

No pattern SHALL become AEOS Core without supporting evidence and review.

## 4. Generalization Boundary

Each pattern SHALL be classified as one of:

- AEOS Core
- AEOS Optional Profile
- Reference Implementation Only
- Do Not Generalize
- Needs More Evidence

This prevents a mechanism from one repository becoming a universal rule without justification.

## 5. Positive Pattern Entry Format

A positive pattern SHALL include:

- pattern ID;
- name;
- category;
- problem;
- context;
- forces;
- solution;
- implementation guidance;
- evidence basis;
- consequences;
- applicability;
- non-applicability;
- generalization classification;
- related patterns;
- related anti-patterns.

## 6. Negative Pattern Entry Format

A negative pattern SHALL include:

- anti-pattern ID;
- name;
- symptom;
- context;
- failure mode;
- why it is harmful;
- evidence basis;
- detection method;
- remediation;
- prevention;
- related positive pattern.

## 7. Initial Positive Patterns

### PAT-001 Repository Truth Before Design

Problem: AI planning often proceeds from stale assumptions.

Solution: Require repository inspection before consequential planning.

Consequences: More accurate plans, slower initial response, fewer implementation reversals.

Classification: AEOS Core.

### PAT-002 Evidence Package as Claim Boundary

Problem: Implementation reports often mix claims and proof.

Solution: Treat implementation reports as claim indexes and evidence packages as proof sources.

Classification: AEOS Core.

### PAT-003 Independent Audit Session

Problem: A planning or implementation session may inherit assumptions.

Solution: Use a fresh audit session or independent reviewer for consequential work.

Classification: AEOS Optional Profile for low-risk work; AEOS Core for high-risk work.

### PAT-004 Approval-Gated Promotion

Problem: Draft outputs and model-generated summaries can become treated as canonical without review.

Solution: Require stage → review → approval → apply for canonicalization.

Classification: AEOS Core.

### PAT-005 Fail-Closed Trust Boundary

Problem: Systems may appear safe when trust evidence is incomplete.

Solution: Missing or stale evidence should degrade trust state and block high-consequence actions.

Classification: AEOS Core.

## 8. Initial Negative Patterns

### ANTI-001 Summary-as-Proof

Symptom: "The agent said it passed."

Failure Mode: Natural-language claims replace inspection.

Remediation: Require evidence package and independent verification.

### ANTI-002 Mergeable-is-Ready

Symptom: PR mergeability is treated as production readiness.

Failure Mode: CI or branch status masks runtime, migration, or operational risk.

Remediation: Separate merge, deployment, production, and operational readiness.

### ANTI-003 Silent Scope Expansion

Symptom: Implementation includes unrelated refactors or design changes.

Failure Mode: Review becomes harder and original objective is obscured.

Remediation: Define out-of-scope items and audit actual diff.

### ANTI-004 Test-Label Inflation

Symptom: A narrow test is cited as proof of broad behavior.

Failure Mode: Confidence exceeds coverage.

Remediation: Map tests to claims and mark unverified criteria explicitly.

### ANTI-005 Disappearing Findings

Symptom: A blocker from one review is absent from the next without disposition.

Failure Mode: Risk is lost.

Remediation: Stable finding IDs and lifecycle status.

## 9. Pattern Review Requirements

Before adopting a pattern, reviewers SHALL ask:

- What evidence supports this pattern?
- Is the pattern specific to one repository?
- What risks does the pattern introduce?
- What is the detection method?
- What would make the pattern invalid?
- Should it be core, optional, reference-only, or rejected?

## 10. Pattern Anti-Patterns

Noncompliant behavior includes:

- promoting preferences as standards;
- generalizing from one anecdote without evidence;
- failing to capture negative consequences;
- omitting non-applicability;
- turning implementation details into universal rules.
