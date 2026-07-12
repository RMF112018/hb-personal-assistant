---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 03 — AEOS Artifact Standard

## 1. Purpose

This standard defines the durable artifacts produced by AEOS-governed work. AEOS is artifact-centric: conversations may initiate and discuss work, but the engineering record SHALL live in repository files, evidence packages, decisions, and review artifacts.

## 2. Artifact Principles

Artifacts SHALL be:

- traceable to source evidence;
- stable enough to survive model/session turnover;
- version-controlled whenever appropriate;
- explicit about assumptions and limitations;
- linked to related artifacts;
- structured consistently across repositories.

## 3. Required Identifiers

Significant artifacts SHOULD use stable identifiers:

- `SPEC-####` for specifications;
- `ADR-####` for architectural decisions;
- `PLAN-####` for implementation plans;
- `EVID-####` for evidence packages;
- `AUDIT-####` for audit reports;
- `FIND-####` for findings;
- `RISK-####` for risks;
- `AC-####` for acceptance criteria;
- `GNG-####` for Go/No-Go records.

Identifiers SHALL NOT be renumbered after review begins.

## 4. Recommended Repository Layout

```text
.ai/
  00_AEOS_MASTER_INDEX.md
  01_AEOS_OPERATING_MANUAL.md
  ...
docs/
  architecture/
  decisions/
  specs/
  implementation-plans/
  evidence/
  audits/
  go-no-go/
  patterns/
```

This layout MAY be adapted to repository conventions, but the artifact types SHALL remain discoverable.

## 5. Repository-Truth Report

### Purpose

Capture current implementation facts before planning or audit.

### Required Fields

- artifact ID;
- date;
- operator/session;
- repository;
- remote;
- branch;
- HEAD SHA;
- base branch and merge base;
- worktree state;
- relevant files inspected;
- tests discovered;
- runtime surfaces discovered;
- verified facts;
- assumptions;
- unknowns;
- evidence gaps;
- next recommended phase.

## 6. Architecture Artifact

### Purpose

Define target design before implementation.

### Required Fields

- artifact ID;
- objective;
- current state;
- desired state;
- affected components;
- interfaces;
- data model;
- trust boundaries;
- failure behavior;
- observability;
- alternatives considered;
- rejected alternatives;
- invariants;
- acceptance criteria;
- risks;
- approval status.

## 7. ADR — Architectural Decision Record

### Purpose

Record durable decisions and rationale.

### Required Fields

- ADR ID;
- title;
- status: proposed, accepted, superseded, rejected;
- date;
- context;
- decision;
- alternatives considered;
- rationale;
- consequences;
- affected repositories;
- related specs;
- supersedes/superseded by;
- evidence references.

ADRs SHOULD be immutable except for status, supersession links, and correction of clerical errors.

## 8. Implementation Plan

### Purpose

Translate approved design into executable work.

### Required Fields

- plan ID;
- objective;
- approved architecture reference;
- repository preflight;
- scope;
- out-of-scope;
- constraints;
- assumptions;
- implementation phases;
- expected files/components;
- tests;
- evidence requirements;
- rollback plan;
- stop conditions;
- required final report format.

## 9. Local-Agent Handoff Prompt

### Purpose

Give a coding agent a complete and bounded execution contract.

### Required Fields

- role;
- repository and branch assumptions;
- mandatory preflight;
- objective;
- scope;
- out-of-scope;
- constraints;
- ordered steps;
- tests;
- evidence;
- forbidden actions;
- stop conditions;
- final report requirements.

## 10. Implementation Report

### Purpose

Provide the implementing agent's claim package.

### Required Fields

- disposition;
- repository state;
- base and head SHAs;
- commits created;
- files changed;
- implementation summary;
- acceptance-criteria matrix;
- tests executed;
- evidence links or pasted output;
- deviations from plan;
- known issues;
- unverified areas;
- final git status.

The report is not proof; it is a claim index for audit.

## 11. Evidence Package

### Purpose

Collect proof for audit and release decisions.

### Required Fields

- evidence package ID;
- repository;
- branch;
- SHAs;
- commands run;
- full command outputs or links;
- test results;
- CI results;
- runtime validation;
- migration validation;
- screenshots if applicable;
- logs;
- baseline comparison;
- known limitations;
- provenance.

## 12. Audit Report

### Purpose

Independently verify implementation claims.

### Required Fields

- audit ID;
- audit scope;
- source evidence reviewed;
- repository state;
- acceptance-criteria matrix;
- finding ledger;
- evidence sufficiency;
- regression assessment;
- security/trust assessment;
- unresolved risks;
- disposition.

## 13. Finding Record

### Required Fields

- finding ID;
- severity;
- title;
- evidence;
- impact;
- root cause or likely cause;
- required remediation;
- verification method;
- status;
- disposition history.

Permitted statuses:

- OPEN;
- FIX CLAIMED;
- VERIFIED FIXED;
- DEFERRED WITH ACCEPTED RISK;
- REJECTED WITH RATIONALE;
- NOT REPRODUCIBLE.

## 14. Corrective Review Report

### Purpose

Verify remediation against findings.

### Required Fields

- original finding IDs;
- claimed fixes;
- evidence reviewed;
- verification result per finding;
- new regressions if any;
- remaining blockers;
- next recommended gate.

## 15. Go/No-Go Record

### Required Fields

- decision ID;
- decision scope;
- target branch/PR/commit;
- readiness category;
- evidence reviewed;
- blockers;
- accepted risks;
- required conditions;
- decision;
- approver;
- timestamp.

## 16. Artifact Quality Rules

Artifacts SHALL NOT:

- hide uncertainty;
- omit known blockers;
- rely on uncited summaries;
- mix unrelated feature scopes;
- overwrite original findings without disposition;
- use vague acceptance criteria;
- treat unverified claims as facts.

## 17. Minimal Artifact Set by Work Type

### Low-Risk Change

- implementation report;
- evidence package;
- lightweight audit or review note.

### Feature Change

- repository-truth report;
- architecture artifact or ADR;
- implementation plan;
- evidence package;
- audit report;
- Go/No-Go if merging or deploying.

### Production or Trust-Boundary Change

All feature artifacts plus:

- production readiness report;
- rollback validation;
- operational watchpoints;
- approval record.
