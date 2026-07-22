---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 08 — AEOS Vocabulary and Taxonomy

## 1. Purpose

This standard defines controlled AEOS terminology for repository truth,
authorization, review identity, lifecycle, evidence representation, readiness,
and closeout.

## 2. Authority Terms

### Repository Truth
Current facts derived from authenticated repository and GitHub inspection.

### Runtime Truth
Current facts derived from the deployed environment and runtime-generated
evidence.

### Publication Truth
Facts about an external publication object, including stable identity, path,
revision, representation, and publication history. Publication truth does not
establish repository execution state.

### Truth Precedence
The ordering used to resolve conflicting factual claims.

### Action Authority
Explicit permission to perform a scoped action against an identified target.
Action authority is distinct from factual truth.

### Operator
The human retaining final decision, authorization, and risk authority.

## 3. Identity Terms

### Base SHA
The immutable commit used as the comparison or authorization baseline.

### Exact Head SHA
The immutable candidate commit to which implementation, evidence, review, or
authorization is bound.

### Reviewed Head
The exact head inspected by an independent reviewer. A later commit makes the
review stale for current-head approval.

### Branch Identity
A stable registration for a local or remote branch, including lifecycle and
expected disposition.

### Worktree Identity
A stable registration for a non-canonical worktree, including path, branch,
base, owner, and disposition.

### Repository Drift
A material change in branch, head, worktree, artifact, environment, or other
identity that may invalidate authorization or evidence.

## 4. Workflow Terms

- **Discovery** — identify current state, risks, unknowns, and evidence needs.
- **Architecture** — define design, boundaries, alternatives, invariants, and
  acceptance criteria.
- **Implementation Planning** — create executable bounded work packages.
- **Plan Review** — independently evaluate a plan before execution.
- **Implementation Audit** — independently evaluate completed work and evidence.
- **Corrective Review** — verify remediation of stable findings.
- **Merge Readiness** — determine whether the exact candidate satisfies merge
  gates; not merge authorization.
- **Merge Authorization** — explicit operator permission to merge an exact
  candidate.
- **Post-Merge Validation** — verify the accepted target-branch identity and
  required post-merge conditions.
- **Branch and Worktree Closeout** — preserve, integrate, retain, remove, or
  block associated repository identities under governed receipts.
- **Deployment Readiness** — determine whether an identified artifact may be
  deployed.
- **Production Readiness** — determine whether a change is safe for production
  use.
- **Operational Readiness** — determine whether the deployed system can be
  supported.

## 5. Lifecycle States

Recommended goal/work lifecycle values:

- `GOVERNANCE_INITIALIZATION`
- `REPOSITORY_TRUTH`
- `ARCHITECTURE`
- `IMPLEMENTATION_PLANNING`
- `PLAN_EXTERNAL_REVIEW`
- `IMPLEMENTATION`
- `IMPLEMENTATION_EXTERNAL_AUDIT`
- `CORRECTIVE_IMPLEMENTATION`
- `CORRECTIVE_EXTERNAL_AUDIT`
- `MERGE_READINESS`
- `MERGE_AUTHORIZATION`
- `MERGED_PENDING_CLEANUP`
- `POST_MERGE_VALIDATION`
- `BRANCH_WORKTREE_CLOSEOUT`
- `BOUNDED_CLOSURE_ASSESSMENT`
- `CLOSED`

Recommended state statuses:

- `NOT_STARTED`
- `IN_PROGRESS`
- `READY_FOR_REVIEW`
- `REVIEW_BLOCKED`
- `BLOCKED`
- `COMPLETE`
- `CLEANUP_AUTHORIZED`
- `RETAINED`
- `CLEANUP_BLOCKED`
- `CLOSED`

## 6. Evidence Terms

### Evidence
Specific, relevant, reproducible proof supporting a claim.

### Claim
A statement not yet independently established by sufficient evidence.

### Evidence Package
An immutable indexed collection of proof for an exact identity and scope.

### Receipt
A durable record that an action occurred, including target, authority,
commands, outputs, timestamps, and disposition.

### Representation
The form of an artifact or evidence item, such as raw file, repository blob,
native Google Doc, export, or runtime observation.

### Hash Scope
The bytes to which a hash applies:

- `stored_raw_bytes`
- `source_bytes`
- `exported_bytes`
- `not_applicable`

### Source Relation
The documented relationship between a publication, source artifact, export, or
derivative.

## 7. Review and Finding Terms

### Independent Context
A reviewer context separated from the implementation context.

### Finding
A stable reviewed defect, gap, risk, or unsupported claim requiring explicit
disposition.

Finding statuses:

- `OPEN`
- `FIX CLAIMED`
- `VERIFIED FIXED`
- `DEFERRED WITH ACCEPTED RISK`
- `REJECTED WITH RATIONALE`
- `NOT REPRODUCIBLE`

Plan/architecture review dispositions:

- `APPROVE`
- `APPROVE WITH REQUIRED CHANGES`
- `REVISE`
- `REJECT`
- `INSUFFICIENT EVIDENCE`

Audit dispositions:

- `PASS`
- `PASS WITH NON-BLOCKING FINDINGS`
- `FAIL — BLOCKERS REMAIN`
- `INSUFFICIENT EVIDENCE`

## 8. Closeout Terms

### Preservation Proof
Evidence that unique, dirty, untracked, inaccessible, or uncertain material was
retained before cleanup.

### Integration Proof
Evidence that branch/worktree content is merged, patch-equivalent, otherwise
integrated, or deliberately retained.

### Cleanup Receipt
Evidence that authorized cleanup actions completed against exact targets.

### Retention Receipt
Evidence that a branch/worktree/ref is intentionally retained with reason,
owner, and review date when applicable.

### Blocker Receipt
Evidence that cleanup or closure stopped safely, including blocker and required
next action.

### No-Prune Fetch
Remote-state refresh that preserves stale refs until inventory and comparison
are complete.

## 9. Readiness Decisions

Merge readiness:

- `READY TO MERGE`
- `READY WITH REQUIRED CONDITIONS`
- `NOT READY`
- `INSUFFICIENT EVIDENCE`

Deployment/production/operational readiness:

- `GO`
- `CONDITIONAL GO`
- `NO-GO`
- `INSUFFICIENT EVIDENCE`

A decision in one category does not imply another.

## 10. Normative Usage

- Use repository truth only for inspected repository/GitHub evidence.
- Use runtime truth only for observed runtime evidence.
- Use action authority only for explicit scoped authorization.
- Use reviewed-head approval only for the exact reviewed head.
- Use `MERGED_PENDING_CLEANUP` after merge until closeout is evidenced.
- Use `CLOSED` only after post-merge validation and a cleanup, retention, or
  blocker disposition.
- Use `GO` only for a bounded readiness decision.
- Never equate native-document identity with source-byte identity.
