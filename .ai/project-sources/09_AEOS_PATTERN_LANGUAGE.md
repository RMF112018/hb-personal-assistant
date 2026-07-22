---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 09 — AEOS Pattern Language

## 1. Purpose

AEOS patterns are evidence-derived engineering practices or failure modes. They
are not preferences promoted without review.

## 2. Promotion Pipeline

```text
Observation
→ Evidence
→ Candidate Pattern
→ Independent Review
→ Classification
→ Pattern Entry
→ Adoption or Rejection
```

Every pattern SHALL identify applicability, non-applicability, evidence basis,
consequences, and generalization classification:

- AEOS Core
- AEOS Optional Profile
- Reference Implementation Only
- Do Not Generalize
- Needs More Evidence

## 3. Positive Pattern Format

A positive pattern includes ID, name, problem, context, forces, solution,
implementation guidance, evidence, consequences, applicability,
non-applicability, classification, and related patterns.

## 4. Negative Pattern Format

A negative pattern includes ID, name, symptom, context, failure mode, harm,
evidence, detection, remediation, prevention, and related positive pattern.

## 5. Core Positive Patterns

### PAT-001 Repository Truth Before Design
Require repository inspection before consequential planning.

### PAT-002 Evidence Package as Claim Boundary
Treat implementation reports as claim indexes and evidence packages as proof
sources.

### PAT-003 Independent Audit Context
Use a separate review context for consequential work.

### PAT-004 Approval-Gated Promotion
Require stage → review → approval → apply before canonicalization or state
transition.

### PAT-005 Fail-Closed Trust Boundary
Missing or stale evidence reduces trust and blocks high-consequence action.

### PAT-006 Exact-Identity Review Binding
Bind review, audit, evidence, and authorization to exact artifact and repository
identity. A later commit invalidates current-head approval.

Classification: AEOS Core.

### PAT-007 Preservation Before Pruning

Problem: cleanup can destroy unique or uncertain repository state before its
relationship to accepted work is known.

Solution: inventory branches, worktrees, refs, tags, dirty state, locks, and
process dependencies; perform no-prune fetch when remote state matters;
preserve unique or uncertain material; prove integration or retention; preview
the exact action; then obtain target-specific authorization.

Classification: AEOS Core for repository cleanup.

### PAT-008 Merge-to-Closeout Lifecycle

Problem: treating merge as closure hides post-merge validation and branch or
worktree disposition.

Solution: transition merge to `MERGED_PENDING_CLEANUP`, perform post-merge
validation, then produce cleanup, retention, or blocker receipts before
closure.

Classification: AEOS Core for governed branch/worktree delivery.

### PAT-009 Representation-Scoped Integrity
Bind hashes and integrity claims to an identified representation and hash scope.
Do not infer byte identity across native documents, sources, and exports.

Classification: AEOS Core.

## 6. Core Negative Patterns

### ANTI-001 Summary-as-Proof
Agent narrative replaces direct evidence.

### ANTI-002 Mergeable-is-Ready
PR mergeability is treated as correctness, deployment, or production evidence.

### ANTI-003 Silent Scope Expansion
Unapproved redesign or unrelated refactoring is hidden inside implementation.

### ANTI-004 Test-Label Inflation
A narrow test is cited as proof of broad behavior.

### ANTI-005 Disappearing Findings
A finding vanishes without explicit disposition.

### ANTI-006 Review-Head Drift
Approval for an earlier head is reused after a later commit.

Remediation: reauthenticate and review the current head.

### ANTI-007 Prune-Before-Proof
Refs, branches, worktrees, or metadata are pruned before complete inventory,
preservation, and integration proof.

Remediation: use PAT-007 and fail closed to preservation.

### ANTI-008 Merge-is-Closure
Merge is used to imply post-merge validation, cleanup, deployment, or closure.

Remediation: use PAT-008.

### ANTI-009 Cross-Representation Hash Equivalence
A hash from an export or source is presented as the hash of a native object, or
vice versa.

Remediation: record representation and hash scope explicitly.

### ANTI-010 Publication-as-Authority
An external publication or chat summary is treated as active repository state or
action authorization.

Remediation: authenticate repository/GitHub state and operator authorization.

## 7. Pattern Review Questions

Before adoption, ask:

- What evidence supports the pattern?
- Which exact repositories, identities, and environments were observed?
- Is the mechanism repository-specific?
- What risks or costs does it introduce?
- How is nonconformance detected?
- What would invalidate the pattern?
- Should it be core, optional, reference-only, rejected, or held for more
  evidence?

## 8. Nonconformance

Do not promote preferences without evidence, generalize from one anecdote,
omit negative consequences, ignore non-applicability, or turn one repository's
implementation detail into a universal rule without review.
