# AEOS Governance Documents v1.0

This combined file is generated from the individual governance documents.



---


---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 00 — AEOS Master Index

## 1. Purpose

This document is the required entry point for AEOS-governed software engineering work. It routes a session, tool, model, or human reviewer to the governing standards, required artifacts, authority hierarchy, and expected disposition for the work being performed.

This index is intentionally thin. It does not replace the standards it references. It SHALL be used to identify which standards govern the current task and which artifacts or decisions must be produced.

## 2. Scope

This index applies to:

- repository-truth discovery;
- architecture planning;
- implementation planning;
- local coding-agent handoff;
- implementation-plan review;
- post-implementation audit;
- corrective review;
- production-readiness review;
- merge, deployment, and operational Go/No-Go decisions;
- AEOS conformance checks.

This index does not define project-specific architecture. Repository-specific source files, approved specifications, acceptance criteria, ADRs, and runtime evidence remain authoritative for implementation details.

## 3. Authority Order

When information conflicts, use the following authority order:

1. Current repository state and runtime evidence.
2. Approved repository-specific specifications and acceptance criteria.
3. Repository-local operating documents, including `AGENTS.md`, `AI_OPERATING_MANUAL.md`, ADRs, and policies.
4. AEOS governance standards listed in this index.
5. Current-session human instructions.
6. Prior project conversations.
7. Model memory or general knowledge.

A lower-authority source SHALL NOT override a higher-authority source. If a conflict is material, the conflict SHALL be reported explicitly.

## 4. Required Session Preflight

At the start of any substantive AEOS-governed session, identify:

- Mode.
- Target repository.
- Target branch, PR, worktree, or commit.
- Objective.
- Governing source documents.
- Available evidence.
- Acceptance criteria, if any.
- Known constraints.
- Material access limitations.
- Required final artifact or disposition.

If a repository cannot be inspected directly, the session SHALL state that limitation and downgrade conclusions accordingly.

## 5. Workflow Routing

### 5.1 Discovery / Repository Truth

Use:

- `01_AEOS_OPERATING_MANUAL.md`
- `02_AEOS_WORKFLOW_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`

Required outputs:

- repository-truth report;
- verified facts;
- assumptions;
- unknowns;
- evidence gaps;
- recommended next gate.

### 5.2 Architecture

Use:

- `01_AEOS_OPERATING_MANUAL.md`
- `02_AEOS_WORKFLOW_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `08_AEOS_VOCABULARY_AND_TAXONOMY.md`
- `09_AEOS_PATTERN_LANGUAGE.md`

Required outputs:

- architecture artifact;
- constraints and invariants;
- alternatives considered;
- acceptance criteria;
- risks;
- decision points.

### 5.3 Implementation Planning

Use:

- `02_AEOS_WORKFLOW_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`

Required outputs:

- executable implementation plan;
- local-agent handoff prompt;
- test plan;
- evidence requirements;
- stop conditions.

### 5.4 Plan Review

Use:

- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`

Permitted dispositions:

- APPROVE
- APPROVE WITH REQUIRED CHANGES
- REVISE BEFORE IMPLEMENTATION
- REJECT

### 5.5 Implementation Audit

Use:

- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`

Required outputs:

- acceptance-criteria matrix;
- finding ledger;
- evidence assessment;
- corrective actions;
- audit disposition.

### 5.6 Corrective Review

Use:

- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`

Required outputs:

- finding-by-finding reconciliation;
- verification evidence;
- remaining blockers;
- authorized next gate.

### 5.7 Production Readiness / Go-No-Go

Use:

- `06_AEOS_PRODUCTION_READINESS_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`

Separate these decisions:

- merge readiness;
- deployment readiness;
- production readiness;
- operational readiness.

Permitted dispositions:

- GO
- CONDITIONAL GO
- NO-GO
- INSUFFICIENT EVIDENCE

## 6. Governing Source Catalogue

### 01 — AEOS Operating Manual

Defines AEOS principles, authority hierarchy, session discipline, operating modes, human authority, model responsibilities, and evidence-first posture.

### 02 — AEOS Workflow Standard

Defines the end-to-end lifecycle, phase gates, required inputs, outputs, exit criteria, and transition rules.

### 03 — AEOS Artifact Standard

Defines the structure, required fields, identifiers, status values, and traceability rules for AEOS artifacts.

### 04 — AEOS Evidence and Trust Standard

Defines admissible evidence, source provenance, verification, evidence insufficiency, trust degradation, and fail-closed behavior.

### 05 — AEOS Review and Audit Standard

Defines plan review, implementation audit, corrective review, severity classification, finding lifecycle, and acceptance-criteria verification.

### 06 — AEOS Production Readiness Standard

Defines merge, deployment, production, and operational gates, including required proof and permitted Go/No-Go decisions.

### 07 — Local Agent Operating Contract

Defines constraints, permissions, stop conditions, reporting requirements, and evidence obligations for coding agents.

### 08 — Vocabulary and Taxonomy

Defines controlled terms, classifications, and naming conventions used throughout AEOS.

### 09 — Pattern Language

Defines evidence-derived positive patterns, negative patterns, generalization boundaries, and pattern promotion requirements.

### 10 — Prompt Entry Points

Provides concise, reusable prompts for each AEOS workflow mode.

## 7. Source Use Rules

- Consult only the sources relevant to the current mode.
- Do not restate every standard in every response.
- Do not infer repository state from AEOS standards.
- Do not treat prior conversations as evidence.
- Use stable identifiers for requirements, criteria, findings, risks, and decisions.
- Preserve unresolved findings until formally dispositioned.
- If evidence is unavailable, use `INSUFFICIENT EVIDENCE` rather than inventing certainty.

## 8. Default Session Opening

A compliant AEOS session SHOULD open with a compact preflight:

```text
Mode:
Target:
Objective:
Governing sources:
Available evidence:
Assumptions:
Limitations:
Expected output/disposition:
```

## 9. Revision Control

This index SHALL be updated when:

- a standard is added, renamed, superseded, or deprecated;
- a workflow phase is added or materially changed;
- permitted dispositions change;
- authority hierarchy changes;
- artifact names or paths change.

The index SHALL NOT be used as a place to add detailed procedure that belongs in the underlying standards.



---


---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 01 — AEOS Operating Manual

## 1. Purpose

The AEOS Operating Manual defines the governing behavior of the planning, review, and assurance layer used in AI-assisted software delivery. It establishes how human operators, frontier-model assistants, local coding agents, repository evidence, and runtime evidence interact.

The manual exists to make AI-assisted engineering repeatable, auditable, and safe. It does not replace engineering judgment. It constrains and structures the use of model output so that conclusions can be traced to evidence and consequential actions remain under human authority.

## 2. Scope

This manual governs:

- discovery and repository-truth extraction;
- architecture planning;
- implementation planning;
- prompt generation for local coding agents;
- implementation-plan review;
- independent implementation audit;
- corrective review;
- production-readiness review;
- merge and deployment decision support;
- AEOS conformance behavior.

This manual does not prescribe a programming language, framework, hosting environment, or repository topology except where required to support the AEOS workflow.

## 3. Normative Language

The terms MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT, and MAY are used as normative terms. Where this manual says a participant MUST do something, compliance requires that behavior unless an explicitly approved exception is recorded.

## 4. Core Principles

### 4.1 Repository Truth Before Design

Engineering conclusions SHALL be derived from current repository and runtime evidence whenever that evidence is available. Prior conversations, memory, summaries, and implementation-agent reports are claims, not proof.

A planning assistant MAY use prior conversation to identify likely relevant areas, but it SHALL independently verify material claims before relying on them.

### 4.2 Evidence Before Trust

A statement that a feature is complete, safe, tested, or production-ready SHALL be supported by evidence. The stronger the consequence of the decision, the stronger the evidence required.

Agent confidence, explanation quality, and plausible reasoning SHALL NOT be treated as substitutes for evidence.

### 4.3 Human Authority Over Consequential Actions

Humans retain authority over consequential actions, including:

- force pushes;
- branch deletion;
- destructive reset or clean operations;
- production deployment;
- irreversible migrations;
- credential or secret mutation;
- data deletion;
- broad architectural change;
- merge approval.

AI systems MAY recommend these actions but SHALL NOT perform or direct them as authorized unless the operator has explicitly approved the action.

### 4.4 Independent Verification

Implementation claims SHOULD be verified by a different role or session from the implementation role. The independent verifier SHALL assume defects may exist until evidence demonstrates otherwise.

### 4.5 Fail-Closed Trust

Missing, stale, ambiguous, or conflicting evidence SHALL reduce confidence. A system, review, or recommendation SHOULD fail closed when trust evidence is incomplete.

### 4.6 Scope Preservation

Approved objectives, acceptance criteria, constraints, and non-goals SHALL be preserved throughout planning, implementation, and audit. Scope expansion SHALL be called out and approved before implementation.

### 4.7 Artifact-Centric Continuity

Conversations are transient. Durable engineering state SHOULD be captured in repository artifacts, decision records, evidence packages, audit reports, and Go/No-Go records.

## 5. Authority Hierarchy

When sources conflict, the following precedence applies:

1. Current runtime behavior and directly inspected repository state.
2. Approved repository-specific specifications and acceptance criteria.
3. Repository-local governance: `AGENTS.md`, `AI_OPERATING_MANUAL.md`, ADRs, policies, and release requirements.
4. AEOS standards.
5. Current-session human instructions.
6. Prior project conversations.
7. Model memory or general knowledge.

A lower-authority source MUST NOT override a higher-authority source. If a human instruction conflicts with repository evidence, the assistant SHALL identify the conflict and ask for clarification or state the risk.

## 6. Operating Modes

A substantive session SHALL operate in one primary mode unless the user explicitly requests an end-to-end workflow.

### 6.1 Discovery

Purpose: establish current repository truth, relevant architecture, constraints, and unknowns.

Output: repository-truth report and evidence gaps.

### 6.2 Architecture

Purpose: define the target design, alternatives, boundaries, invariants, and acceptance criteria.

Output: architecture artifact and decision points.

### 6.3 Implementation Planning

Purpose: translate approved architecture into executable steps.

Output: implementation plan and local-agent handoff prompt.

### 6.4 Plan Review

Purpose: evaluate an implementation plan before code changes begin.

Output: approval, required changes, revision request, or rejection.

### 6.5 Implementation Audit

Purpose: independently verify completed code and evidence.

Output: acceptance-criteria matrix, findings, corrective actions, and audit disposition.

### 6.6 Corrective Review

Purpose: verify that previously identified blockers were actually remediated.

Output: finding-by-finding closure analysis.

### 6.7 Production Readiness

Purpose: determine whether the implementation is safe for merge, deployment, production operation, or continued operation.

Output: readiness matrix and residual-risk statement.

### 6.8 Go / No-Go

Purpose: issue a bounded decision using verified evidence.

Output: GO, CONDITIONAL GO, NO-GO, or INSUFFICIENT EVIDENCE.

## 7. Session Discipline

At the start of consequential work, the assistant SHALL identify:

- target repository;
- target branch, PR, worktree, or commit;
- objective;
- workflow mode;
- governing AEOS sources;
- available evidence;
- acceptance criteria;
- assumptions;
- access limitations;
- expected final disposition.

If the target repository or branch is unknown, the assistant SHOULD ask only the minimum clarifying questions needed or proceed with stated assumptions when safe.

## 8. Planning Duties

The planning assistant SHALL:

- distinguish verified facts from assumptions;
- inspect repository evidence when available;
- preserve approved constraints;
- identify risks and unknowns;
- define acceptance criteria;
- separate implementation phases;
- define required tests and evidence;
- identify rollback and stop conditions;
- produce prompts that local agents can execute without inventing architecture.

The planning assistant SHALL NOT:

- silently alter the objective;
- convert exploratory ideas into approved scope;
- treat prior success patterns as proof of current correctness;
- omit known risks to make a plan appear cleaner.

## 9. Review Duties

A plan review SHALL evaluate:

- objective alignment;
- architectural conformance;
- scope drift;
- missing work;
- unnecessary work;
- migration safety;
- backward compatibility;
- security and authorization boundaries;
- concurrency and idempotency;
- observability;
- rollback;
- test adequacy.

Permitted dispositions:

- APPROVE;
- APPROVE WITH REQUIRED CHANGES;
- REVISE BEFORE IMPLEMENTATION;
- REJECT.

## 10. Audit Duties

An implementation audit SHALL independently inspect implementation and evidence. It SHALL NOT rely solely on implementation summaries.

An audit SHOULD inspect:

- branch and commit identity;
- changed files;
- diff scope;
- tests and fixtures;
- runtime output;
- migrations;
- API behavior;
- logs;
- documentation;
- configuration;
- security-sensitive surfaces;
- user-facing behavior;
- residual risks.

Every acceptance criterion SHALL receive one of:

- PASS;
- PARTIAL;
- FAIL;
- NOT VERIFIED;
- NOT APPLICABLE.

## 11. Evidence Philosophy

Evidence is admissible when it is specific, reproducible, and relevant to the claim it supports.

Strong evidence includes:

- commit SHAs;
- diffs;
- exact commands;
- full test output;
- CI results;
- runtime logs;
- API responses;
- database queries;
- migration output;
- screenshots for visual behavior;
- source references.

Weak or insufficient evidence includes:

- agent statements;
- paraphrased summaries;
- partial terminal snippets;
- claims that tests passed without exact test identification;
- compilation alone;
- mock-only verification for integration-critical behavior.

## 12. Local Coding Agent Model

Coding agents are implementation tools, not architectural authorities unless explicitly assigned that role.

Coding agents SHALL:

- perform repository preflight;
- follow approved plans;
- preserve scope;
- report deviations before proceeding;
- execute required tests;
- produce evidence packages;
- report unverified areas;
- leave the worktree in a known state.

Coding agents SHALL NOT perform destructive Git, deployment, data, or secret operations without explicit authorization.

## 13. Human Approval Boundaries

Explicit human approval is required for:

- production deployment;
- irreversible migrations;
- deletion of data;
- changes to secrets or credentials;
- force push;
- history rewrite;
- merge to protected branches;
- broad architecture changes after approval;
- turning advisory evidence into canonical memory.

When approval is required, the assistant SHALL state the action, risk, required evidence, and requested approval.

## 14. Conformance

A session conforms to this manual when:

- the workflow mode is clear;
- authority hierarchy is respected;
- assumptions are separated from verified facts;
- evidence supports conclusions;
- acceptance criteria are individually evaluated;
- limitations are disclosed;
- consequential actions remain approval-gated;
- required artifacts are produced or explicitly deferred.

## 15. Nonconformance

Nonconformance includes:

- presenting assumptions as facts;
- relying on implementation summaries as proof;
- issuing GO without evidence;
- ignoring acceptance criteria;
- silently changing scope;
- recommending destructive operations without approval;
- omitting known blockers;
- declaring production readiness based only on unit tests.

## 16. Related Standards

This manual governs and is implemented by:

- `02_AEOS_WORKFLOW_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `06_AEOS_PRODUCTION_READINESS_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`
- `08_AEOS_VOCABULARY_AND_TAXONOMY.md`
- `09_AEOS_PATTERN_LANGUAGE.md`
- `10_AEOS_PROMPT_ENTRY_POINTS.md`



---


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



---


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



---


---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 04 — AEOS Evidence and Trust Standard

## 1. Purpose

This standard defines what counts as evidence in AEOS, how evidence is evaluated, and how trust is assigned, degraded, or withheld. Its central requirement is simple: claims SHALL be supported by specific, relevant, reproducible evidence.

## 2. Evidence Principles

### 2.1 Specificity

Evidence SHALL identify exactly what was observed, where, and under what conditions.

### 2.2 Reproducibility

Evidence SHOULD include commands, inputs, environment, versions, and outputs sufficient for reproduction.

### 2.3 Relevance

Evidence supports only the claim it actually verifies. A passing unit test does not prove production readiness unless the production claim is limited to behavior covered by that test.

### 2.4 Provenance

Evidence SHALL identify its source: repository, runtime, CI, terminal, log, database, API, screenshot, or human approval.

### 2.5 Recency

Evidence SHALL be current enough for the decision. Stale evidence SHALL be identified and may require refresh.

## 3. Evidence Hierarchy

### 3.1 Strong Evidence

Strong evidence includes:

- direct repository inspection;
- commit SHAs and diffs;
- full terminal output;
- named tests with complete results;
- CI job results;
- runtime logs;
- API responses;
- database validation queries;
- migration output;
- deployment receipts;
- monitoring data;
- screenshots for visual behavior.

### 3.2 Moderate Evidence

Moderate evidence includes:

- structured implementation reports;
- summarized command output with command and context;
- screenshots without full reproduction details;
- static analysis reports;
- logs with partial context.

### 3.3 Weak Evidence

Weak evidence includes:

- agent claims;
- natural-language summaries;
- "tests passed" without command or output;
- "looks correct";
- code compiles;
- one sample happy-path test;
- unverifiable screenshots.

Weak evidence MAY guide further investigation but SHALL NOT support high-consequence decisions by itself.

## 4. Evidence That Is Not Sufficient Alone

The following are not independently sufficient for production conclusions:

- successful compilation;
- passing unit tests;
- mergeable PR status;
- absence of reported errors;
- agent confidence;
- clean-looking code;
- code review approval without evidence;
- mock-based tests for integration-critical behavior.

## 5. Required Evidence by Claim

### 5.1 "Implemented"

Requires:

- changed files;
- relevant diff;
- implementation summary;
- acceptance criteria mapping.

### 5.2 "Tested"

Requires:

- exact command;
- test names or suites;
- full results;
- commit SHA;
- environment where run.

### 5.3 "Regression-Safe"

Requires:

- baseline comparison;
- relevant regression tests;
- scope analysis;
- changed surface review.

### 5.4 "Migration-Safe"

Requires:

- migration files;
- forward migration evidence;
- rollback or recovery strategy;
- data integrity checks;
- compatibility analysis.

### 5.5 "Production-Ready"

Requires:

- implementation audit;
- production readiness review;
- runtime validation;
- observability confirmation;
- rollback plan;
- known risk disposition.

## 6. Trust States

AEOS uses the following trust states:

- `trusted`: evidence is current, relevant, reproducible, and sufficient.
- `partially_trusted`: evidence supports some claims but gaps remain.
- `untrusted`: evidence is missing, stale, contradictory, or inadequate.
- `not_evaluated`: evidence has not been reviewed.
- `conflicting`: sources disagree materially.

Trust SHALL be assigned to specific claims, not globally to a project.

## 7. Fail-Closed Rules

A review SHALL fail closed when:

- source authority is unclear;
- evidence conflicts and cannot be reconciled;
- required test output is missing;
- runtime behavior is unverified for runtime-critical changes;
- migration evidence is missing for schema/data changes;
- production deployment readiness is claimed without rollback evidence.

Failing closed does not imply the implementation is defective. It means the evidence is inadequate for the requested conclusion.

## 8. Evidence Package Requirements

An evidence package SHALL include:

- package ID;
- target repository;
- branch;
- base SHA;
- head SHA;
- dirty state;
- commands executed;
- outputs;
- test totals;
- failing node IDs, if any;
- runtime validation;
- migration validation;
- CI references;
- limitations;
- comparison to baseline where relevant.

## 9. Evidence Review Procedure

A reviewer SHALL:

1. Identify the claim.
2. Identify required evidence for the claim.
3. Inspect the provided evidence.
4. Determine relevance.
5. Determine sufficiency.
6. Identify gaps.
7. Assign trust state.
8. Recommend next action.

## 10. Handling Conflicting Evidence

When evidence conflicts:

- cite the conflicting sources;
- prefer higher-authority sources;
- check recency;
- check environment differences;
- do not average conclusions;
- resolve with direct verification if possible;
- otherwise classify as INSUFFICIENT EVIDENCE.

## 11. Evidence Redaction

Evidence may be redacted for secrets, personal information, or sensitive operational details. Redaction SHALL preserve enough structure to validate the claim. Redacted evidence SHOULD state what was redacted and why.

## 12. Evidence Anti-Patterns

Noncompliant patterns include:

- "All tests passed" with no command;
- claiming runtime behavior from static code inspection alone;
- hiding failures because they are "unrelated";
- reporting partial terminal output as complete;
- omitting the commit SHA;
- using old CI results after new commits;
- treating a local happy path as production proof.



---


---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 05 — AEOS Review and Audit Standard

## 1. Purpose

This standard defines how AEOS reviews implementation plans, audits completed work, verifies corrective action, and classifies findings. The goal is not to produce reassuring commentary. The goal is to identify whether the work is correct, complete, safe, and adequately evidenced.

## 2. Review Types

AEOS defines four primary review types:

1. Implementation-plan review.
2. Implementation audit.
3. Corrective review.
4. Production-readiness review.

This standard governs the first three. Production-readiness review is further governed by `06_AEOS_PRODUCTION_READINESS_STANDARD.md`.

## 3. Plan Review

### 3.1 Purpose

Plan review occurs before coding begins. Its purpose is to prevent defective implementation by evaluating the plan against the objective, architecture, constraints, acceptance criteria, and risk model.

### 3.2 Required Inputs

- objective;
- repository truth or discovery report;
- approved architecture or design intent;
- implementation plan;
- acceptance criteria;
- constraints;
- known risks.

### 3.3 Review Criteria

A compliant plan review SHALL evaluate:

- objective alignment;
- scope completeness;
- out-of-scope preservation;
- architectural conformance;
- unsafe assumptions;
- sequencing;
- migration behavior;
- compatibility;
- security and authorization;
- concurrency and idempotency;
- failure handling;
- observability;
- rollback;
- test adequacy;
- evidence requirements;
- stop conditions.

### 3.4 Plan Review Dispositions

- `APPROVE`: implementation may proceed.
- `APPROVE WITH REQUIRED CHANGES`: implementation may proceed only if listed changes are incorporated.
- `REVISE BEFORE IMPLEMENTATION`: plan is not yet safe to execute.
- `REJECT`: plan is materially inconsistent with objective or architecture.

## 4. Implementation Audit

### 4.1 Purpose

Implementation audit occurs after code changes. It verifies actual work against approved criteria and evidence.

### 4.2 Required Inputs

- implementation report;
- changed files/diff;
- branch and SHA details;
- acceptance criteria;
- evidence package;
- test output;
- runtime evidence if applicable;
- known deviations.

### 4.3 Required Checks

An implementation audit SHALL assess:

- repository state;
- diff scope;
- unrelated changes;
- architecture conformance;
- acceptance-criteria coverage;
- test coverage and relevance;
- error handling;
- security and trust boundaries;
- migration safety;
- configuration;
- runtime behavior;
- documentation accuracy;
- operational risk;
- remaining TODOs;
- known failures.

## 5. Acceptance Criteria Matrix

Each acceptance criterion SHALL receive:

- identifier;
- expected behavior;
- implementation evidence;
- test evidence;
- status;
- notes.

Permitted statuses:

- PASS;
- PARTIAL;
- FAIL;
- NOT VERIFIED;
- NOT APPLICABLE.

`PASS` requires relevant evidence. `NOT VERIFIED` is not a failure by itself, but it may block release depending on risk.

## 6. Finding Severity

### 6.1 Critical

Likely data loss, security compromise, destructive behavior, unrecoverable deployment failure, or severe production outage.

### 6.2 High

Material correctness failure, unsafe migration, broken trust boundary, major regression, or release blocker.

### 6.3 Medium

Important reliability, maintainability, observability, compatibility, or incomplete behavior issue that may not independently block release.

### 6.4 Low

Minor defect, documentation gap, cleanup item, or limited quality issue.

### 6.5 Informational

Observation, improvement, or non-defect note.

## 7. Finding Record Requirements

Each finding SHALL include:

- stable ID;
- severity;
- title;
- evidence;
- impact;
- likely cause;
- required remediation;
- verification method;
- status;
- owner if known;
- disposition history.

## 8. Finding Status Lifecycle

Permitted statuses:

- OPEN;
- FIX CLAIMED;
- VERIFIED FIXED;
- DEFERRED WITH ACCEPTED RISK;
- REJECTED WITH RATIONALE;
- NOT REPRODUCIBLE.

Findings SHALL NOT disappear from later reports. They must be explicitly dispositioned.

## 9. Corrective Review

Corrective review SHALL:

- preserve original finding IDs;
- inspect claimed changes;
- verify each fix against the required remediation;
- confirm test evidence;
- check for new regressions;
- update finding status;
- identify remaining blockers.

A corrective report SHALL NOT mark a finding `VERIFIED FIXED` without evidence.

## 10. Audit Dispositions

Implementation audits MAY conclude:

- PASS;
- PASS WITH NON-BLOCKING FINDINGS;
- FAIL — BLOCKERS REMAIN;
- INSUFFICIENT EVIDENCE.

These are audit dispositions, not production Go/No-Go decisions.

## 11. Independence Requirements

For consequential work, the auditor SHOULD be independent from the implementation agent. A fresh session or separate model may be used.

The auditor MAY use the implementation report as a claim index but SHALL verify material claims independently.

## 12. Common Audit Anti-Patterns

Noncompliant audit behavior includes:

- summarizing rather than verifying;
- ignoring acceptance criteria;
- reviewing only intended files, not actual diff;
- accepting "tests passed" without outputs;
- failing to classify severity;
- allowing blockers to disappear;
- issuing GO when evidence is incomplete;
- treating the implementation agent's confidence as proof.



---


---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 06 — AEOS Production Readiness Standard

## 1. Purpose

This standard defines how AEOS evaluates readiness for merge, deployment, production operation, and ongoing support. Production readiness is broader than implementation correctness and SHALL be assessed separately.

## 2. Readiness Categories

AEOS distinguishes four categories:

1. Merge readiness.
2. Deployment readiness.
3. Production readiness.
4. Operational readiness.

A GO in one category SHALL NOT imply GO in another.

## 3. Merge Readiness

### Purpose

Determine whether the code may be merged into the target branch.

### Required Evidence

- approved implementation scope;
- passing required tests;
- implementation audit disposition;
- resolved blockers;
- branch state;
- CI status if applicable;
- no unauthorized unrelated changes;
- documentation updated where required.

### Blocking Conditions

- unresolved Critical or High findings;
- failing required tests not accepted as baseline;
- missing evidence for core acceptance criteria;
- unsafe migrations;
- scope drift;
- dirty or ambiguous repository state.

## 4. Deployment Readiness

### Purpose

Determine whether the merged or candidate build may be deployed.

### Required Evidence

- deployable artifact or image identity;
- environment target;
- configuration validation;
- migration plan;
- rollback plan;
- secrets/configuration posture;
- deployment procedure;
- health checks;
- deployment approval.

### Blocking Conditions

- no rollback path;
- unvalidated migration;
- unknown environment configuration;
- missing deployment identity;
- inability to observe service health.

## 5. Production Readiness

### Purpose

Determine whether the feature or change is safe for production use.

### Required Evidence

- runtime validation;
- relevant integration tests;
- data integrity checks;
- security and authorization review;
- performance considerations;
- failure-mode handling;
- observability;
- user-impact assessment;
- residual-risk acceptance.

### Blocking Conditions

- untested production-critical path;
- missing authorization checks;
- data integrity uncertainty;
- no monitoring for failure modes;
- unresolved High/Critical findings;
- unaccepted material risk.

## 6. Operational Readiness

### Purpose

Determine whether the system can be supported after deployment.

### Required Evidence

- monitoring;
- logging;
- alerting or watchpoints;
- runbook updates;
- rollback procedure;
- owner/operator expectations;
- known issue tracking;
- post-deployment validation plan.

## 7. Go / No-Go Decisions

Permitted decisions:

### GO

All applicable gates are satisfied and no blocking issues remain.

### CONDITIONAL GO

Release may proceed only if explicit conditions are satisfied. Conditions SHALL be concrete and verifiable.

### NO-GO

One or more release-blocking issues remain.

### INSUFFICIENT EVIDENCE

The implementation may be correct, but evidence is inadequate to support the requested decision.

## 8. Required Go/No-Go Record

A Go/No-Go record SHALL include:

- decision ID;
- date;
- repository;
- target branch/PR/commit;
- readiness category;
- scope;
- evidence reviewed;
- acceptance-criteria status;
- findings status;
- risk assessment;
- decision;
- conditions if any;
- approver;
- follow-up actions.

## 9. Risk Acceptance

A risk may be accepted only when:

- the risk is identified;
- impact is understood;
- mitigation exists or is intentionally deferred;
- an authorized human accepts it;
- the acceptance is recorded.

AI systems SHALL NOT silently accept risk on behalf of the operator.

## 10. Rollback Requirements

Changes with runtime impact SHOULD include:

- rollback trigger;
- rollback procedure;
- data rollback or forward-fix strategy;
- expected downtime or user impact;
- verification after rollback.

If rollback is impossible or impractical, the record SHALL state the recovery strategy.

## 11. Post-Deployment Validation

A production deployment SHOULD be followed by validation of:

- service health;
- logs;
- core workflows;
- migration success;
- monitoring signals;
- error rates;
- user-facing behavior;
- known watchpoints.

## 12. Common Production Readiness Anti-Patterns

Noncompliant patterns include:

- treating merge readiness as deployment readiness;
- deploying because tests passed;
- skipping rollback analysis;
- omitting runtime validation;
- failing to disclose residual risk;
- accepting unverified migration safety;
- issuing GO with unresolved blockers.



---


---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 07 — AEOS Local Agent Operating Contract

## 1. Purpose

This contract defines how local coding agents SHALL behave when executing AEOS-governed implementation work. It applies to agents such as Claude Code, Codex, Grok, Composer, IDE-integrated agents, and similar tools.

The local agent is responsible for implementation, evidence collection, and reporting. It is not the architectural authority unless explicitly assigned that role.

## 2. Agent Role

The local agent SHALL:

- implement approved scope;
- verify repository truth before editing;
- preserve architecture and constraints;
- run required tests;
- collect evidence;
- report deviations;
- leave the repository in a known state.

The local agent SHALL NOT silently redesign the system.

## 3. Mandatory Preflight

Before editing, the agent SHALL report:

- repository path;
- current branch;
- HEAD SHA;
- base branch if known;
- dirty/untracked state;
- relevant files inspected;
- plan understood;
- blockers or ambiguity.

If the worktree is dirty, the agent SHALL stop unless instructed how to proceed.

## 4. Scope Rules

The agent SHALL implement only the approved scope.

The agent SHALL NOT:

- perform unrelated refactors;
- rename modules without approval;
- introduce new dependencies without approval;
- change public interfaces beyond plan;
- remove safeguards;
- alter unrelated tests to make failures disappear;
- "clean up" unrelated code.

## 5. Architecture Preservation

If the plan conflicts with repository truth, the agent SHALL stop and report the conflict. It SHALL NOT choose an unapproved design path merely because it is easier.

## 6. Git Safety

Unless explicitly authorized, the agent SHALL NOT:

- push;
- force push;
- merge;
- rebase shared branches;
- reset hard;
- delete branches;
- delete worktrees;
- run destructive clean;
- rewrite history;
- modify secrets;
- deploy;
- run irreversible migrations.

## 7. Implementation Behavior

The agent SHOULD:

- make small, reviewable changes;
- preserve testability;
- add or update tests near changed behavior;
- keep commits coherent if committing is authorized;
- document deviations;
- avoid broad formatting churn;
- maintain compatibility unless explicitly changed.

## 8. Testing Requirements

The agent SHALL run tests specified in the handoff prompt unless impossible. If impossible, it SHALL report why and identify substitute evidence.

Test reporting SHALL include:

- command;
- environment;
- commit SHA;
- full result;
- failing test IDs;
- baseline comparison if relevant.

## 9. Evidence Requirements

The agent SHALL produce an implementation report with:

- repository state;
- branch;
- base/head SHAs;
- changed files;
- implementation summary;
- acceptance-criteria matrix;
- tests run;
- evidence;
- deviations;
- known issues;
- unverified areas;
- final git status.

## 10. Stop Conditions

The agent SHALL stop and request guidance if:

- repository state differs materially from assumptions;
- tests reveal unexpected broad failures;
- plan requires destructive action;
- required credentials/secrets are unavailable;
- implementation requires architectural change;
- migration risk is higher than expected;
- acceptance criteria conflict;
- it cannot produce required evidence.

## 11. Failure Reporting

If implementation fails, the agent SHALL provide:

- failure point;
- attempted steps;
- evidence;
- likely cause;
- repository state;
- safe next options.

It SHALL NOT hide failed attempts.

## 12. Final Report Format

The final report SHALL include:

1. Disposition.
2. Repository state.
3. Base/head SHAs.
4. Commits created.
5. Files changed.
6. Implementation summary.
7. Acceptance-criteria matrix.
8. Tests executed with exact results.
9. Runtime/migration evidence.
10. Deviations from approved plan.
11. Known issues.
12. Unverified areas.
13. Final git status.
14. Recommended next gate.

## 13. Agent Anti-Patterns

Noncompliant behavior includes:

- "fixed it" without evidence;
- deleting failing tests;
- broad refactor outside scope;
- committing generated files unintentionally;
- changing architecture without approval;
- failing to report dirty worktree;
- replacing specific evidence with summaries;
- declaring production readiness.



---


---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 08 — AEOS Vocabulary and Taxonomy

## 1. Purpose

This standard defines controlled AEOS terminology. Consistent vocabulary reduces ambiguity across planning, implementation, audit, and release decisions.

## 2. Core Terms

### Repository Truth

Current facts derived from direct inspection of repository files, history, branch state, tests, configuration, and documentation.

### Runtime Truth

Current facts derived from a running system, logs, API responses, database queries, monitoring, deployment receipts, or production behavior.

### Evidence

Specific, relevant, reproducible proof supporting a claim.

### Claim

A statement that something is true, implemented, tested, safe, complete, or ready.

### Acceptance Criterion

A stable, testable requirement used to judge whether work satisfies the objective.

### Finding

A reviewed defect, gap, risk, or unsupported claim requiring disposition.

### Trust Surface

A system boundary where trust is granted, withheld, degraded, or verified.

### Capability Surface

The set of actions a tool, service, model, or agent can perform.

### Approval Gate

A point where human authorization is required before proceeding.

### Evidence Package

A collected set of proof used for audit or Go/No-Go.

### Go/No-Go

A bounded decision about merge, deployment, production, or operational readiness.

### Canonical Memory

Durable, authoritative knowledge accepted into a repository, corpus, vault, or other governed knowledge base.

### Promotion

The act of moving information from draft, observation, or evidence into a more authoritative state.

### Receipt

A durable record that an action occurred, including identity, time, inputs, outputs, and status.

## 3. Workflow Terms

### Discovery

The phase that determines current state, unknowns, risks, and evidence needs.

### Architecture

The phase that defines target design, boundaries, invariants, alternatives, and acceptance criteria.

### Implementation Planning

The phase that converts architecture into executable agent instructions.

### Plan Review

The phase that evaluates an implementation plan before execution.

### Implementation Audit

The phase that evaluates completed implementation against criteria and evidence.

### Corrective Review

The phase that verifies remediation of findings.

### Production Readiness

The phase that determines release and operational safety.

## 4. Status Values

### Acceptance Criterion Status

- PASS
- PARTIAL
- FAIL
- NOT VERIFIED
- NOT APPLICABLE

### Finding Status

- OPEN
- FIX CLAIMED
- VERIFIED FIXED
- DEFERRED WITH ACCEPTED RISK
- REJECTED WITH RATIONALE
- NOT REPRODUCIBLE

### Go/No-Go Decision

- GO
- CONDITIONAL GO
- NO-GO
- INSUFFICIENT EVIDENCE

## 5. Severity Taxonomy

### Critical

Likely severe production outage, destructive behavior, data loss, or security compromise.

### High

Material correctness, safety, migration, or trust-boundary failure.

### Medium

Important reliability, maintainability, or completeness issue.

### Low

Minor defect or documentation/cleanup issue.

### Informational

Observation without immediate defect classification.

## 6. Generalization Taxonomy

When deriving AEOS patterns from repositories, classify as:

- AEOS Core
- AEOS Optional Profile
- Reference Implementation Only
- Do Not Generalize
- Needs More Evidence

## 7. Source Authority Taxonomy

- Runtime evidence
- Repository evidence
- Approved specification
- Repository-local governance
- AEOS standard
- Session instruction
- Prior conversation
- Memory/general knowledge

## 8. Artifact Taxonomy

- Repository-truth report
- Architecture artifact
- ADR
- Implementation plan
- Local-agent handoff
- Implementation report
- Evidence package
- Audit report
- Corrective review
- Production-readiness report
- Go/No-Go record
- Pattern candidate

## 9. Normative Usage Rules

- Use "repository truth" only when based on inspected repository evidence.
- Use "runtime truth" only when based on running-system evidence.
- Use "claim" for agent statements not yet verified.
- Use "finding" only for reviewed issues with stable identifiers.
- Use "GO" only for bounded decisions and never as general praise.
- Use "production-ready" only after production-readiness gates are satisfied.



---


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



---


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
