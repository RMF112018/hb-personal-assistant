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
