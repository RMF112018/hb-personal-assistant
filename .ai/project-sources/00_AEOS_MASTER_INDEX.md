---
standard: AEOS
version: "1.3"
status: normative
license: internal-use
---

# 00 — AEOS Master Index

## 1. Purpose

This document is the required entry point for AEOS-governed software engineering
work. It routes a session, tool, model, or human reviewer to the governing
standards, repository-local controls, required artifacts, evidence standard,
authority boundary, and expected disposition.

This index is intentionally thin. It does not replace the standards it
references and does not establish repository or runtime truth.

## 2. Scope

This index applies to:

- repository-truth discovery;
- architecture;
- implementation planning;
- plan review;
- implementation execution;
- evidence packaging;
- implementation audit;
- corrective implementation and review;
- finding reconciliation;
- merge readiness and merge authorization;
- post-merge validation;
- branch and worktree closeout;
- deployment, production, and operational readiness;
- Go/No-Go decisions;
- AEOS conformance checks.

Repository-specific implementation, accepted ADRs, policies, approved
specifications, authenticated GitHub state, and runtime evidence remain
authoritative for their applicable domains.

## 3. Truth Precedence and Action Authority

### 3.1 Truth precedence

When factual sources conflict, use:

1. authenticated runtime evidence for deployed behavior;
2. authenticated repository and GitHub state for engineering identity and
   lifecycle;
3. repository-local governance, accepted ADRs, approved specifications, and
   acceptance criteria;
4. AEOS standards;
5. approved publication/reference governance for publication matters;
6. prior conversations and agent reports as claim indexes;
7. model memory or general knowledge.

A lower-authority source SHALL NOT override a higher-authority source. Material
conflicts SHALL be reported explicitly.

### 3.2 Action authority

The current operator instruction defines task intent and permitted scope. It
does not alter factual evidence or approve work by implication.

The operator retains final decision, authorization, and risk authority.
Repository access, Workspace access, publication state, a prior approval, or
tool capability SHALL NOT be treated as action authority.

## 4. Repository-Specific Control Plane

For `RMF112018/hb-personal-assistant`, also read the current accepted repository controls:

```text
AI_OPERATING_MANUAL.md
AGENTS.md
docs/decisions/ADR-019-github-first-engineering-control-plane.md
docs/governance/branch-worktree-lifecycle-policy.md
docs/implementation-plans/github-first-control-plane-migration.md
.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md
```

The repository and authenticated GitHub state are canonical for active
engineering state. Runtime evidence is canonical for deployed behavior. Google
Drive is an approved publication/reference surface and must not maintain a
competing active-state ledger.

ADR-019 Phase A is merged at
`8b44cbd216d531a1894b4257355469edf922029f`. The lifecycle remains
`MERGED_PENDING_CLEANUP`; cleanup requires separate authorization. Phase B
remains separately unauthorized.

## 5. Required Session Preflight

At the start of substantive work, identify:

- operating mode;
- target repository and authenticated remote;
- issue or goal;
- work item;
- authorization identifier;
- branch and worktree identities;
- base SHA and exact head SHA;
- pull request and required checks, when applicable;
- review identity and reviewed head, when applicable;
- lifecycle state and checkpoint;
- objective;
- governing sources;
- available and inaccessible evidence;
- acceptance criteria;
- constraints and stop conditions;
- required artifact or bounded disposition.

If repository or GitHub state can be authenticated, do not proceed on a
material identity assumption. Runtime claims require runtime evidence.

## 6. Workflow Routing

### 6.1 Discovery / Repository Truth

Use:

- `01_AEOS_OPERATING_MANUAL.md`
- `02_AEOS_WORKFLOW_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md` when branch/worktree inventory is material

Required outputs:

- repository-truth report;
- exact repository identity;
- branch/worktree/ref inventory when material;
- verified facts;
- assumptions and unknowns;
- evidence gaps;
- recommended next gate.

### 6.2 Architecture

Use:

- `01_AEOS_OPERATING_MANUAL.md`
- `02_AEOS_WORKFLOW_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `08_AEOS_VOCABULARY_AND_TAXONOMY.md`
- `09_AEOS_PATTERN_LANGUAGE.md`

Required outputs:

- architecture artifact;
- constraints and invariants;
- alternatives;
- acceptance criteria;
- risks;
- decision points.

### 6.3 Implementation Planning

Use:

- `02_AEOS_WORKFLOW_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md`

Required outputs:

- executable implementation plan;
- branch/worktree ownership and expected closeout disposition;
- local-agent handoff prompt;
- proportional test plan and failure-disposition rules;
- evidence and representation requirements;
- rollback and stop conditions.

### 6.4 Plan or Architecture Review

Use:

- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md` when test scope is material

Permitted dispositions:

- `APPROVE`
- `APPROVE WITH REQUIRED CHANGES`
- `REVISE`
- `REJECT`
- `INSUFFICIENT EVIDENCE`

A review SHALL identify the exact artifact and repository head reviewed.

### 6.5 Implementation Execution

Use:

- `02_AEOS_WORKFLOW_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md`

Required outputs:

- bounded implementation receipt;
- exact base/head identity;
- changed-file and work-item traceability;
- proportional test evidence;
- deviations and stop conditions;
- final repository state.

### 6.6 Evidence Packaging

Use:

- `03_AEOS_ARTIFACT_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`

Required outputs:

- immutable run identity;
- representation-aware evidence index;
- exact commands, outputs, and exit codes;
- artifact hashes scoped to identified representations;
- limitations and redaction receipts.

### 6.7 Implementation Audit

Use:

- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md`

Required outputs:

- reviewed exact head SHA;
- acceptance-criteria matrix;
- finding ledger;
- evidence and test-selection assessment;
- audit disposition.

### 6.8 Corrective Review and Finding Reconciliation

Use:

- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md` when failures or parallel correction are involved

Required outputs:

- finding-by-finding reconciliation;
- corrected exact head identity;
- closure evidence;
- remaining blockers;
- bounded next-gate recommendation.

### 6.9 Merge Readiness and Authorization

Use:

- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `06_AEOS_PRODUCTION_READINESS_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md`

Required outputs:

- exact candidate head;
- current-head independent review;
- required checks and applicable safe-suite status;
- unresolved finding and failure status;
- explicit operator merge authorization or non-authorization.

Mergeability is not merge authorization.

### 6.10 Post-Merge Validation and Branch/Worktree Closeout

Use:

- `02_AEOS_WORKFLOW_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`
- repository `POL-GIT-HYGIENE-001`

Required outputs:

- accepted merge identity;
- post-merge validation or explicit not-required decision;
- preservation and integration proof;
- worktree, local branch, remote branch, metadata, and remote-ref dispositions;
- cleanup, retention, or blocker receipt.

A merge moves work to `MERGED_PENDING_CLEANUP`, not directly to `CLOSED`.

### 6.11 Deployment / Production / Operational Readiness

Use:

- `06_AEOS_PRODUCTION_READINESS_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md`

Evaluate separately:

- deployment readiness;
- production readiness;
- operational readiness.

Permitted decisions:

- `GO`
- `CONDITIONAL GO`
- `NO-GO`
- `INSUFFICIENT EVIDENCE`

## 7. Governing Source Catalogue

- `01_AEOS_OPERATING_MANUAL.md` — authority, operating modes, session discipline, and evidence-first behavior.
- `02_AEOS_WORKFLOW_STANDARD.md` — lifecycle, gates, transitions, merge, post-merge validation, and closeout.
- `03_AEOS_ARTIFACT_STANDARD.md` — artifact identity, traceability, representation, and required records.
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md` — admissible evidence, exact identity, representation scope, and trust.
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md` — independent review, exact-head binding, findings, and dispositions.
- `06_AEOS_PRODUCTION_READINESS_STANDARD.md` — merge, cleanup, deployment, production, and operational gates.
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md` — agent permissions, repository hygiene, tests, evidence, and stops.
- `08_AEOS_VOCABULARY_AND_TAXONOMY.md` — controlled terms and lifecycle values.
- `09_AEOS_PATTERN_LANGUAGE.md` — evidence-derived patterns and anti-patterns.
- `10_AEOS_PROMPT_ENTRY_POINTS.md` — reusable entry prompts.
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md` — proportional test selection, failure disposition, isolated corrective work, and integrated-green requirements.

## 8. Source Use Rules

- Consult only sources relevant to the active mode.
- Do not infer repository state from AEOS standards.
- Do not treat prior conversations or agent reports as proof.
- Use stable identifiers for requirements, findings, risks, decisions, branches,
  worktrees, authorizations, reviews, and evidence.
- Bind reviews and audits to exact artifact and repository identities.
- Preserve unresolved findings and failing-test evidence until dispositioned.
- Do not declare merge readiness while an applicable required-safe suite has an
  unresolved failure.
- Do not transition from merge directly to closure.
- Use `INSUFFICIENT EVIDENCE` rather than inventing certainty.

## 9. Default Session Opening

```text
Mode:
Repository / authenticated remote:
Issue or goal:
Work item:
Branch / worktree:
Base SHA:
Exact head SHA:
Pull request / checks:
Authorization:
Objective:
Governing sources:
Available evidence:
Limitations:
Expected artifact or disposition:
```

## 10. Revision Control

Update this index when a standard, workflow phase, disposition, authority model,
identity requirement, or governed artifact changes. Detailed procedure belongs
in the underlying standards.
