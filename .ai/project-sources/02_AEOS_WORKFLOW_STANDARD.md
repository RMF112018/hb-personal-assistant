---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 02 — AEOS Workflow Standard

## 1. Purpose

This standard defines the AEOS engineering lifecycle. It establishes phases, entry criteria, exit criteria, required outputs, evidence expectations, and transition rules for AI-assisted software delivery.

The workflow exists to prevent the common failure mode of moving directly from idea to generated code without repository truth, explicit acceptance criteria, independent review, or production evidence.

## 2. Lifecycle Overview

The normative AEOS lifecycle is:

```text
Intake
→ Discovery
→ Repository Truth
→ Architecture
→ Implementation Planning
→ Plan Review
→ Implementation
→ Evidence Collection
→ Implementation Audit
→ Corrective Review
→ Production Readiness
→ Go / No-Go
→ Merge
→ Deployment
→ Post-Deployment Validation
→ Learning / Corpus Promotion
```

Not every change requires every phase. The required rigor SHALL be proportional to risk, but phase skipping SHALL be explicit.

## 3. Phase Classification

### 3.1 Mandatory for Consequential Work

For features, migrations, security changes, trust-boundary changes, production behavior changes, or architectural changes, the following are mandatory:

- Discovery / Repository Truth;
- Architecture or design intent;
- Implementation Plan;
- Evidence Collection;
- Implementation Audit;
- Go / No-Go.

### 3.2 Optional for Low-Risk Work

For trivial documentation or cosmetic changes, phases MAY be condensed if:

- the scope is narrow;
- no runtime behavior changes;
- no production risk;
- no security or data integrity impact;
- no architecture change.

The decision to condense SHALL be stated.

## 4. Intake

### Purpose

Clarify the user objective and determine whether AEOS governance applies.

### Inputs

- user request;
- repository or project name;
- desired outcome;
- urgency and constraints.

### Required Output

- workflow mode;
- target repository;
- initial scope;
- immediate next phase.

### Exit Criteria

The request is routed to Discovery, Architecture, Implementation Planning, Review, Audit, or Go/No-Go.

## 5. Discovery

### Purpose

Understand the problem, existing system behavior, constraints, and open questions.

### Activities

- identify relevant repository surfaces;
- inspect documentation and code paths;
- identify related tests and fixtures;
- find prior decisions or ADRs;
- identify runtime dependencies;
- classify risks and unknowns.

### Output

Repository-truth discovery report.

### Exit Criteria

The current state is sufficiently understood to plan architecture or identify needed evidence.

## 6. Repository Truth

### Purpose

Establish the evidence baseline.

### Required Checks

Where possible, capture:

- repository name and remote;
- current branch;
- HEAD SHA;
- base branch and merge base;
- dirty/untracked state;
- relevant commits;
- relevant files;
- current tests;
- runtime entry points;
- schemas and migrations;
- configuration and feature flags;
- known failures.

### Output

Repository-truth report with verified facts, assumptions, and evidence gaps.

### Exit Criteria

The session can distinguish actual implementation from assumptions.

## 7. Architecture

### Purpose

Define the desired design before implementation.

### Required Content

- objective;
- target behavior;
- affected surfaces;
- interfaces;
- data model;
- failure behavior;
- security and authorization model;
- observability;
- alternatives considered;
- rejected alternatives;
- constraints and invariants;
- acceptance criteria.

### Output

Architecture artifact or ADR.

### Exit Criteria

The implementation direction is approved or ready for implementation planning.

## 8. Implementation Planning

### Purpose

Translate architecture into executable steps for a local coding agent.

### Required Content

- repository preflight instructions;
- scope and out-of-scope;
- phases;
- expected file areas;
- tests;
- evidence requirements;
- stop conditions;
- implementation report format.

### Output

Implementation plan and local-agent prompt.

### Exit Criteria

The coding agent can execute the work without inventing architecture.

## 9. Plan Review

### Purpose

Prevent defective implementation before code is written.

### Review Criteria

- objective alignment;
- scope control;
- missing phases;
- unsafe sequencing;
- migration risk;
- security and trust boundaries;
- observability;
- rollback;
- tests and evidence.

### Output

One disposition:

- APPROVE;
- APPROVE WITH REQUIRED CHANGES;
- REVISE BEFORE IMPLEMENTATION;
- REJECT.

### Exit Criteria

The plan is approved or returned for revision.

## 10. Implementation

### Purpose

Perform code changes according to the approved plan.

### Agent Duties

- confirm branch and worktree;
- inspect relevant repository truth;
- implement only approved scope;
- run required tests;
- capture evidence;
- stop at approval gates;
- produce implementation report.

### Exit Criteria

Implementation report and evidence package are ready for independent audit.

## 11. Evidence Collection

### Purpose

Create reproducible proof for claims.

### Required Evidence

As applicable:

- git status;
- changed files;
- commit SHAs;
- exact test commands and full results;
- CI links/results;
- migration output;
- runtime validation;
- API responses;
- logs;
- screenshots;
- known limitations.

### Exit Criteria

Evidence is complete enough to support or reject implementation claims.

## 12. Implementation Audit

### Purpose

Independently determine whether the approved work was implemented correctly.

### Activities

- inspect actual diff;
- compare to acceptance criteria;
- review tests;
- identify regressions;
- assess evidence;
- classify findings;
- assign disposition.

### Output

Audit report.

### Exit Criteria

The implementation is passed, blocked, or sent to corrective review.

## 13. Corrective Review

### Purpose

Verify remediation of previously identified findings.

### Activities

- preserve original finding IDs;
- verify each claimed fix;
- compare new evidence to prior evidence;
- identify remaining blockers;
- prevent new scope drift.

### Output

Corrective-review report.

### Exit Criteria

Each finding is dispositioned.

## 14. Production Readiness

### Purpose

Assess release safety beyond code correctness.

### Gates

- merge readiness;
- deployment readiness;
- production readiness;
- operational readiness.

### Output

Readiness report.

### Exit Criteria

A bounded Go/No-Go decision can be issued.

## 15. Go / No-Go

### Purpose

Provide a final release decision based on evidence.

### Dispositions

- GO;
- CONDITIONAL GO;
- NO-GO;
- INSUFFICIENT EVIDENCE.

### Required Content

- decision scope;
- evidence reviewed;
- unresolved findings;
- accepted risks;
- required follow-ups.

## 16. Merge

Merge SHALL occur only after the applicable readiness decision permits it and repository rules allow it.

Merge decisions SHALL NOT imply deployment readiness unless explicitly stated.

## 17. Deployment

Deployment SHALL require deployment-specific evidence, rollback plan, and operator approval where consequential.

## 18. Post-Deployment Validation

After deployment, verify:

- service health;
- logs;
- migrations;
- user-facing behavior;
- monitoring;
- rollback readiness;
- known risk watchpoints.

## 19. Learning / Corpus Promotion

After a feature closes, patterns or lessons MAY be proposed for the AEOS corpus. Promotion requires evidence, review, and classification under the Pattern Language Standard.

## 20. Workflow Anti-Patterns

The following are noncompliant:

- implementation before repository truth;
- plan approval without acceptance criteria;
- audit based only on agent summary;
- GO based only on unit tests;
- untracked corrective findings;
- scope expansion hidden inside implementation;
- treating mergeability as deployability.
