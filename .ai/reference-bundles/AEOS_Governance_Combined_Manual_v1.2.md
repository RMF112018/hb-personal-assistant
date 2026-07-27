# AEOS Governance Documents v1.2

This non-canonical convenience bundle is generated from the individual governing source files. The source files remain authoritative.


---

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


---

---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 01 — AEOS Operating Manual

## 1. Purpose

This manual governs the planning, review, implementation-control, evidence, and
assurance layer used in AI-assisted software delivery. It makes work repeatable,
auditable, and safe without replacing engineering judgment.

## 2. Core Principles

1. **Repository truth before design.** Verify material repository and GitHub
   claims before relying on them.
2. **Runtime truth for deployed behavior.** Plans and code inspection do not
   establish actual runtime behavior.
3. **Evidence before trust.** Confidence, narrative quality, and agent reports
   are not proof.
4. **Human authority over consequential action.** Models may recommend but may
   not self-authorize.
5. **Independent verification.** Consequential implementation and review use
   separate contexts.
6. **Fail closed.** Missing, stale, ambiguous, or conflicting evidence reduces
   the allowable confidence.
7. **Scope preservation.** Changes to objective, architecture, constraints, or
   acceptance criteria require explicit disposition.
8. **Artifact-centric continuity.** Durable state belongs in governed
   repository, evidence, decision, and publication artifacts.

## 3. Truth Precedence

When factual sources conflict:

1. authenticated runtime evidence for deployed behavior;
2. authenticated repository and GitHub state for engineering identity and
   lifecycle;
3. repository-local governance, accepted ADRs, approved specifications, and
   acceptance criteria;
4. AEOS standards;
5. approved publication/reference governance for publication matters;
6. prior conversations and agent reports as claim indexes;
7. model memory or general knowledge.

A lower-authority source SHALL NOT override a higher-authority source.

## 4. Action Authority

The current operator instruction defines task intent and permitted scope. It
does not change factual evidence or approve an unstated action.

The operator retains final decision, authorization, and risk authority.
Repository access, Workspace access, publication status, prior approval, or
tool capability does not grant action authority.

Without explicit operator authorization, a model SHALL NOT:

- merge or force-push;
- rewrite history;
- delete branches, worktrees, refs, data, or evidence;
- prune worktree metadata or remote references;
- deploy or activate production;
- mutate secrets or credentials;
- run irreversible migrations;
- accept risk;
- approve its own implementation as independent review;
- activate the next governed state.

## 5. GitHub-First Engineering State

Repository content and authenticated GitHub issues, branches, worktrees,
commits, pull requests, reviews, checks, and merge state are canonical for
engineering execution.

Drive and other publication surfaces may publish or reference engineering
identities but SHALL NOT independently define or activate the active goal, work
item, authorization, branch, SHA, PR, review, merge state, or checkpoint.

Repository-specific governance MAY impose stronger controls. For
`RMF112018/hb-personal-assistant`, ADR-019 and `POL-GIT-HYGIENE-001` govern.
Merge transitions work to `MERGED_PENDING_CLEANUP`, not directly to `CLOSED`.

## 6. Required Session Preflight

Before substantive work, identify:

- operating mode;
- repository and authenticated remote;
- issue or goal;
- work item and authorization;
- branch and worktree identities;
- base SHA and exact head SHA;
- pull request and checks;
- review identity and reviewed head, when applicable;
- lifecycle state and checkpoint;
- objective and expected artifact;
- governing sources;
- evidence and access limitations;
- acceptance criteria;
- constraints and stop conditions.

Do not proceed on a material identity assumption when the state can be
authenticated.

## 7. Operating Modes

Use one primary mode unless an end-to-end workflow is explicitly authorized:

- Discovery / Repository Truth
- Architecture
- Goal Engineering
- Implementation Planning
- Plan Review
- Implementation Execution
- Evidence Packaging
- Implementation Audit
- Corrective Review
- Finding Reconciliation
- Merge Readiness
- Post-Merge Validation
- Branch and Worktree Closeout
- Deployment Readiness
- Production Readiness
- Go / No-Go
- Pattern / Corpus Review

Planning, implementation, independent review, merge authorization, cleanup,
deployment, and production decisions SHALL remain distinct.

## 8. Goal and State Discipline

A governed invocation has exactly one active state. The model may execute only
the authorized state and may request but not activate the next state.

Authorization SHALL identify the goal, work item, transition or action,
repository identity, expected branch/worktree, and expected head where
applicable. Repository drift invalidates authorization unless the authorization
explicitly permits the changed identity.

A later commit invalidates current-head review approval.

## 9. Branch and Worktree Discipline

Register every non-canonical branch and worktree before substantive editing.

Inventory, no-prune fetch, preservation, and integration proof SHALL precede
pruning or deletion. Worktree removal, local branch deletion, remote branch
deletion, worktree metadata pruning, and remote-reference pruning are separate
actions.

Closure after merge requires:

- accepted merge identity;
- post-merge validation or explicit not-required decision;
- preservation/disposition of dirty and untracked material;
- integration or retention proof;
- worktree, local branch, and remote branch disposition;
- cleanup, retention, or blocker receipt.

## 10. Evidence and Trust

Evidence SHALL be specific, relevant, reproducible, current, and bound to the
claim it supports.

Record as applicable:

- repository, branch, worktree, base SHA, and exact head SHA;
- environment and runtime identity;
- commands, exit codes, outputs, and timestamps;
- tests and failure classifications;
- artifact representation, MIME type, hash scope, and SHA-256;
- limitations, redactions, and unavailable evidence.

Valid hash scopes are:

- `stored_raw_bytes`
- `source_bytes`
- `exported_bytes`
- `not_applicable`

Hashes from different representation classes are not interchangeable. A native
Google Doc has stable object identity and revision history but no portable
raw-byte SHA-256.

## 11. Durable Artifacts and Publication

Repository engineering artifacts remain canonical in the repository and
GitHub. Publication artifacts may provide collaboration and external handoff.

A durable publication SHOULD record:

- title;
- classification and artifact type;
- status and version;
- stable publication identity and logical path;
- purpose;
- representation and hash scope;
- canonical repository or GitHub pointer.

Publication does not imply approval, implementation, audit passage, merge
readiness, deployment readiness, production readiness, or authorization.

## 12. Reviews and Decisions

A plan or architecture review may conclude:

- `APPROVE`
- `APPROVE WITH REQUIRED CHANGES`
- `REVISE`
- `REJECT`
- `INSUFFICIENT EVIDENCE`

An implementation audit may conclude:

- `PASS`
- `PASS WITH NON-BLOCKING FINDINGS`
- `FAIL — BLOCKERS REMAIN`
- `INSUFFICIENT EVIDENCE`

Readiness decisions are separately scoped and may conclude:

- `GO`
- `CONDITIONAL GO`
- `NO-GO`
- `INSUFFICIENT EVIDENCE`

Every disposition SHALL identify exact scope, identity, evidence basis,
blockers, conditions, and residual risk.

## 13. Conformance

A conforming session:

- authenticates material identity;
- distinguishes truth from authorization;
- separates verified facts from claims and assumptions;
- binds evidence and review to exact identities;
- preserves scope and unresolved findings;
- uses proportional tests and classifies failures;
- stops at authorization boundaries;
- preserves state when evidence or authority is insufficient;
- produces or explicitly defers required durable artifacts.

## 14. Related Standards

- `02_AEOS_WORKFLOW_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `06_AEOS_PRODUCTION_READINESS_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`
- `08_AEOS_VOCABULARY_AND_TAXONOMY.md`
- `09_AEOS_PATTERN_LANGUAGE.md`
- `10_AEOS_PROMPT_ENTRY_POINTS.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md`


---

---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 02 — AEOS Workflow Standard

## 1. Purpose

This standard defines the AEOS lifecycle, phase gates, required inputs and
outputs, evidence expectations, transition rules, and closeout controls.

## 2. Normative Lifecycle

```text
Intake
→ Discovery
→ Repository Truth
→ Architecture, when required
→ Implementation Planning
→ Independent Plan Review
→ Authorized Implementation
→ Evidence Packaging
→ Independent Implementation Audit
→ Authorized Corrective Implementation, when required
→ Independent Corrective Audit
→ Merge Readiness
→ Explicit Merge Authorization
→ Merge
→ Post-Merge Validation
→ Branch and Worktree Cleanup, Retention, or Blocker Receipt
→ Bounded Closure
→ Separately Authorized Deployment Readiness
→ Deployment
→ Post-Deployment Validation
→ Production / Operational Readiness
→ Learning / Corpus Promotion
```

Rigor SHALL be proportional to risk, but phase condensation or omission SHALL
be explicit and evidenced.

## 3. Universal Transition Rules

Every transition SHALL identify:

- goal and work item;
- source and destination state;
- operator authorization;
- repository and authenticated remote;
- branch and worktree identities;
- base and exact head SHA;
- pull request and checks when applicable;
- required artifacts and evidence;
- actor and timestamp;
- stop conditions.

A model may request but SHALL NOT activate the next state. Repository drift
invalidates identity-bound authorization and current-head review.

## 4. Intake and Discovery

Intake establishes objective, repository, operating mode, initial scope,
constraints, and immediate next gate.

Discovery identifies relevant:

- implementation and tests;
- schemas and migrations;
- configuration and CI;
- repository governance and ADRs;
- runtime and deployment surfaces;
- prior evidence and known failures;
- risks and unknowns.

Output: bounded discovery or repository-truth request.

## 5. Repository Truth

Capture, where available:

- repository and authenticated remote;
- default and current branches;
- registered branch and worktree identities;
- base SHA, exact head SHA, and merge base;
- dirty and untracked state;
- pull request, required checks, and review state;
- relevant commits, files, tests, schemas, migrations, and configuration;
- local worktrees, remote refs, tags, locks, and process dependencies when
  hygiene or cleanup is material;
- runtime surfaces and available runtime evidence;
- verified facts, assumptions, unknowns, and unavailable evidence.

Repository truth is read-only unless artifact publication is separately
authorized.

## 6. Architecture

Architecture defines:

- objective and target behavior;
- affected components and interfaces;
- data and trust boundaries;
- failure behavior and authorization;
- observability and rollback;
- alternatives and rejected alternatives;
- invariants, risks, and acceptance criteria.

Architecture output SHALL be independently reviewed when consequential.

## 7. Implementation Planning

An executable plan SHALL include:

- authoritative baseline and exact identity;
- branch/worktree ownership and expected disposition;
- scope and out-of-scope;
- ordered work packages;
- expected files and symbols;
- acceptance traceability;
- proportional test plan under
  `11_REPOSITORY_TEST_SELECTION_STANDARD.md`;
- failure-classification and integrated-green requirements;
- evidence and representation contract;
- rollback and recovery;
- prohibitions, retry limits, and stop conditions;
- final report and review checkpoints;
- expected post-merge validation and closeout requirements.

## 8. Plan Review

Plan review evaluates objective alignment, architecture, scope, sequencing,
security, migration behavior, compatibility, observability, rollback, tests,
evidence, repository hygiene, and stop conditions.

Permitted dispositions:

- `APPROVE`
- `APPROVE WITH REQUIRED CHANGES`
- `REVISE`
- `REJECT`
- `INSUFFICIENT EVIDENCE`

The review SHALL identify the reviewed artifact version and repository identity.

## 9. Authorized Implementation

Before editing, verify:

- branch and worktree registration;
- exact branch and head;
- work-item authorization;
- plan and artifact hashes;
- prerequisites;
- dirty-state disposition;
- scope and prohibited actions.

Implement only the authorized work package. Preserve unrelated state. Stop on
architecture drift, scope expansion, unexpected migration or side effects,
test-infrastructure defects, conflicting criteria, or exhausted retry limits.

## 10. Proportional Testing and Failure Disposition

Use the repository test-selection standard. Validation SHALL proceed from
narrow direct tests to affected-domain bundles and applicable cross-cutting
canaries, with broader suites when risk or policy requires them.

Every failing test SHALL be preserved and classified. Separate corrective work
requires separate authorization and isolated branch/worktree ownership. The
combined candidate remains blocked until applicable required-safe suites have
zero unresolved failures.

## 11. Evidence Packaging

Package immutable evidence with:

- run identity;
- exact repository and environment identity;
- commands, timestamps, exit codes, stdout, and stderr;
- test and CI results;
- diff and artifact manifests;
- representation and hash scope;
- failed and invalid attempts;
- limitations and redactions.

Evidence collection does not decide sufficiency.

## 12. Independent Implementation Audit

The auditor SHALL inspect actual diff and evidence at the exact head. It SHALL
not repair the implementation.

Required output:

- acceptance-criteria matrix;
- test-selection and failure assessment;
- finding ledger;
- evidence sufficiency assessment;
- exact reviewed head;
- audit disposition.

A later commit makes the audit stale for current-head approval.

## 13. Corrective Implementation and Audit

Corrective work SHALL preserve finding IDs and history. The implementation
context may propose `CLAIMED_NOT_VERIFIED` but may not set `VERIFIED FIXED`.

Independent corrective audit SHALL bind each closure decision to the corrected
exact head and closure evidence.

## 14. Merge Readiness

Merge readiness requires:

- approved scope and exact candidate identity;
- current-head independent review or audit;
- passing required checks;
- zero unresolved failures in applicable required-safe suites;
- no unresolved blocking findings;
- no unauthorized unrelated changes;
- clean or explicitly governed repository state;
- documented post-merge validation and closeout plan.

Mergeability is not readiness and readiness is not authorization.

## 15. Merge Authorization and Merge

Only explicit operator authorization may permit merge. Authorization SHALL bind
to the exact PR/head and method or constraints when material.

Merge moves the lifecycle to `MERGED_PENDING_CLEANUP`. It does not authorize
cleanup, deployment, production activation, or closure.

## 16. Post-Merge Validation

Post-merge validation SHALL identify:

- accepted main or target-branch commit;
- relationship to the reviewed candidate;
- required checks or tests at the accepted identity;
- documentation or index reconciliation;
- runtime validation when applicable;
- unresolved follow-up or explicit not-required decisions.

## 17. Branch and Worktree Closeout

Before deletion or pruning:

1. inventory all relevant branches, worktrees, refs, tags, dirty state, locks,
   and process dependencies;
2. perform no-prune fetch when remote state is material;
3. preserve unique or uncertain material;
4. prove integration, patch equivalence, retention need, or blocker;
5. preview and separately authorize each destructive or pruning action.

Worktree removal, local branch deletion, remote branch deletion, worktree
metadata pruning, and remote-reference pruning are distinct actions.

Closeout output SHALL be a cleanup, retention, or blocker receipt. Only then may
the work item move to `CLOSED`.

## 18. Deployment and Production Lifecycle

Deployment requires a separately authorized deployment identity, target
environment, configuration validation, migration and rollback plan, health
checks, and deployment receipt.

Post-deployment validation evaluates runtime health, logs, migrations,
monitoring, error rates, user-facing behavior, and rollback readiness.

Production and operational readiness remain separate from merge and deployment.

## 19. Workflow Anti-Patterns

Noncompliant behavior includes:

- implementation before repository truth;
- plan approval without criteria or identity;
- audit based on agent summary;
- review not bound to exact head;
- merge treated as closure or deployment authority;
- pruning before inventory and preservation;
- hidden test failures or disappearing findings;
- Drive or chat state used as competing engineering authority;
- cross-representation hash claims;
- GO based only on compilation or unit tests.


---

---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 03 — AEOS Artifact Standard

## 1. Purpose

AEOS is artifact-centric. Durable engineering state belongs in governed
repository files, evidence packages, decisions, reviews, lifecycle records, and
approved publication artifacts—not only in conversations.

## 2. Universal Artifact Requirements

A significant artifact SHALL identify, as applicable:

- stable artifact ID;
- title and artifact type;
- status and version;
- author or execution context;
- created and modified timestamps;
- objective and scope;
- canonical repository and authenticated remote;
- issue, goal, and work item;
- authorization identifier;
- branch and worktree identifiers;
- base SHA and exact head SHA;
- pull request and required checks;
- reviewed head and review identity;
- lifecycle state and checkpoint;
- governing sources;
- acceptance criteria;
- evidence references;
- assumptions, limitations, and unknowns;
- related and superseding artifacts.

Identifiers SHALL NOT be silently renumbered after review begins.

## 3. Representation and Integrity

When an artifact is material to an integrity claim, record:

```yaml
representation:
mime_type:
hash_scope:
sha256:
source_relation:
verification:
```

Valid representation examples:

- `raw_file`
- `native_google_doc`
- `exported_representation`
- `repository_blob`
- `runtime_observation`

Valid hash scopes:

- `stored_raw_bytes`
- `source_bytes`
- `exported_bytes`
- `not_applicable`

A SHA-256 authenticates only the identified representation and scope. Hashes
from different representation classes SHALL NOT be treated as equivalent. A
native Google Doc SHALL use `hash_scope: not_applicable` unless a separately
identified source or export is hashed.

## 4. Canonical Locations

Repository artifacts SHOULD use established locations:

```text
.ai/aeos/goals/<goal-id>/
docs/architecture/
docs/decisions/
docs/governance/
docs/specs/
docs/implementation-plans/
docs/evidence/
docs/audits/
docs/go-no-go/
```

Publication copies MAY exist in approved external systems but SHALL identify
their canonical repository or GitHub pointer when one exists.

## 5. Repository-Truth Report

Required fields include:

- repository and remote;
- default branch and target branch;
- branch/worktree registration;
- base, head, and merge-base SHAs;
- dirty/untracked state;
- PR, checks, and review state;
- relevant files, tests, schemas, migrations, configuration, and runtime
  surfaces;
- branch, worktree, ref, tag, lock, and process inventory when hygiene is in
  scope;
- verified facts, claims not verified, assumptions, unknowns, and unavailable
  evidence;
- evidence gaps and next gate.

## 6. Architecture and ADR Artifacts

Architecture artifacts SHALL define objective, current and desired state,
components, interfaces, data and trust boundaries, failure behavior,
observability, alternatives, invariants, acceptance criteria, risks, and
approval status.

ADRs SHALL record context, decision, alternatives, rationale, consequences,
status, affected repositories, supersession, and evidence. Accepted ADRs are
immutable except for status, supersession links, and clerical corrections.

## 7. Implementation Plan and Handoff

An implementation plan SHALL include:

- authoritative baseline and exact identity;
- branch/worktree ownership and expected disposition;
- approved architecture;
- scope and out-of-scope;
- work packages and prerequisites;
- expected files and symbols;
- acceptance traceability;
- proportional test plan;
- failure-disposition rules;
- evidence and representation contract;
- rollback and recovery;
- prohibited actions and stop conditions;
- independent review checkpoints;
- post-merge validation and closeout expectations;
- required final report.

A local-agent handoff SHALL reproduce the bounded execution contract without
inventing additional authority.

## 8. Work-Item Ledger

Each work item SHALL record:

- stable work-item ID;
- title and lifecycle status;
- authorization ID;
- branch and worktree identity;
- base and expected head;
- prerequisites;
- scope and out-of-scope;
- acceptance criteria;
- tests and evidence;
- retry limit and stop conditions;
- expected merge and closeout disposition;
- actual disposition and related receipts.

## 9. Implementation Report

An implementation report is a claim index, not proof. It SHALL include:

- exact repository state and identity;
- commits and changed files;
- implementation summary;
- acceptance-criteria matrix;
- test commands and outcomes;
- failing-test classifications;
- evidence references;
- deviations;
- known issues and unverified areas;
- final git status;
- recommended next gate.

## 10. Evidence Index and Package

An evidence index SHALL include, per item:

```yaml
evidence_id:
path:
kind:
representation:
mime_type:
hash_scope:
sha256:
claim_ids:
generated_by:
repository_head:
environment:
status:
```

Evidence packages SHALL preserve failed and invalid attempts, raw or native
machine output, commands, exit codes, timestamps, redactions, and limitations.

## 11. Review and Audit Artifacts

A review or audit SHALL identify:

- review/audit ID and type;
- independent context and limitations;
- reviewed artifact versions;
- repository, branch, PR, base, and exact reviewed head;
- evidence reviewed;
- acceptance-criteria matrix;
- findings and severities;
- required changes or closure tests;
- disposition;
- stale-on-head-change rule;
- operator decision state.

A later commit SHALL make current-head approval stale.

## 12. Finding Record

Each finding SHALL preserve:

- stable ID;
- severity and title;
- affected criterion;
- exact repository identity;
- evidence;
- impact and likely cause;
- required remediation;
- closure test;
- status and owner;
- disposition history;
- risk-acceptance identity when applicable.

Findings SHALL NOT disappear without explicit disposition.

## 13. Merge and Closeout Artifacts

### 13.1 Merge-readiness record

Record exact candidate head, PR, checks, current-head review, safe-suite status,
blocking findings, unrelated changes, required conditions, and operator
authorization state.

### 13.2 Post-merge validation record

Record accepted target-branch commit, relationship to candidate, validation
performed, not-required decisions, and remaining follow-up.

### 13.3 Cleanup, retention, or blocker receipt

Record:

- complete inventory basis;
- preservation actions;
- integration or patch-equivalence proof;
- worktree disposition;
- local branch disposition;
- remote branch disposition;
- metadata and remote-ref prune previews/actions;
- separate authorization IDs;
- commands, outputs, and timestamps;
- retained material or blockers;
- final lifecycle state.

Merge alone is not a closeout receipt.

## 14. Readiness and Go/No-Go Records

Readiness artifacts SHALL separate:

- merge readiness;
- cleanup/closure readiness;
- deployment readiness;
- production readiness;
- operational readiness.

A decision record SHALL identify exact target identity, evidence, blockers,
conditions, accepted risks, approver, and timestamp.

## 15. Publication Registration

A durable external publication SHOULD record:

- title;
- classification and artifact type;
- status and version;
- stable external identity and logical path;
- purpose;
- representation and hash scope;
- nearest owning publication index;
- canonical repository or GitHub pointer.

Publication does not imply approval or action authority.

## 16. Artifact Quality Rules

Artifacts SHALL NOT:

- hide uncertainty or blockers;
- use duplicate titles as identity;
- rely on uncited summaries;
- mix unrelated scopes;
- overwrite findings or failed evidence;
- use vague acceptance criteria;
- claim cross-representation byte identity;
- treat publication, review, merge, deployment, and production as one state.


---

---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 04 — AEOS Evidence and Trust Standard

## 1. Purpose

This standard defines admissible evidence, provenance, exact-identity binding,
representation scope, trust states, insufficiency, and fail-closed behavior.

## 2. Evidence Principles

Evidence SHALL be:

- **specific** — identify exactly what was observed;
- **reproducible** — include commands, inputs, environment, and outputs;
- **relevant** — support only the claim actually verified;
- **provenanced** — identify repository, runtime, CI, tool, or human source;
- **current** — be fresh enough for the decision;
- **identity-bound** — identify the exact artifact, SHA, environment, or runtime
  observation;
- **representation-aware** — identify which bytes or native object are
  authenticated.

Agent narrative and prior conversations are claim indexes, not proof.

## 3. Evidence Authority

For deployed behavior, authenticated runtime evidence has priority. For
engineering identity and lifecycle, authenticated repository and GitHub state
has priority. Approved specifications and governance define expected behavior
but do not prove implementation or runtime results.

Publication systems are authoritative for their own object identity and
publication history, not for repository execution state.

## 4. Exact Repository Identity

Material repository evidence SHALL record, as applicable:

- repository and authenticated remote;
- default and target branch;
- worktree identity and path;
- base SHA, exact head SHA, and merge base;
- pull request and required checks;
- dirty/untracked state;
- reviewed or tested head;
- accepted merge identity.

Evidence from one head SHALL NOT be presented as current-head evidence after a
later commit without re-verification.

## 5. Representation and Hash Scope

Each material evidence item SHOULD record:

```yaml
representation:
mime_type:
hash_scope:
sha256:
source_relation:
verification:
```

Valid hash scopes:

- `stored_raw_bytes`
- `source_bytes`
- `exported_bytes`
- `not_applicable`

A hash authenticates only the identified representation. Cross-representation
hash equivalence SHALL NOT be inferred.

A native Google Doc has stable Drive identity and revision history but no
portable raw-byte SHA-256. Its publication identity may be verified, while
source-byte or export-byte claims require separately identified evidence.

## 6. Evidence Strength

### Strong evidence

- authenticated repository state and diffs;
- exact commit SHAs;
- full command output and exit codes;
- named tests with complete results;
- CI checks bound to exact head;
- runtime logs and API responses;
- database validation;
- migration and deployment receipts;
- monitoring data;
- representation-scoped hashes.

### Moderate evidence

- structured implementation reports;
- summarized output with command and context;
- static analysis;
- partial logs or screenshots with limitations.

### Weak evidence

- agent claims;
- uncited summaries;
- "tests passed" without identity or output;
- compilation alone;
- mock-only proof for integration-critical behavior;
- publication receipt offered as technical correctness evidence.

Weak evidence SHALL NOT support high-consequence conclusions alone.

## 7. Required Evidence by Claim

### Implemented

Requires diff, changed files, exact head, implementation summary, and acceptance
traceability.

### Tested

Requires exact command, suite or node IDs, complete results, exact head, and
environment.

### Regression-safe

Requires proportional test selection, changed-surface analysis, failure
classification, and applicable required-safe suites.

### Migration-safe

Requires migration identity, forward evidence, recovery strategy, data
integrity checks, and compatibility analysis.

### Reviewed or approved

Requires review identity, independent context, exact reviewed artifact and head,
evidence basis, disposition, and stale-on-head-change rule.

### Merged

Requires authenticated accepted target-branch identity. It does not prove
cleanup, deployment, or production readiness.

### Closed

Requires post-merge validation or explicit not-required decision plus a cleanup,
retention, or blocker receipt.

### Production-ready

Requires separately scoped implementation audit, runtime validation,
observability, rollback, and risk disposition.

## 8. Evidence Package Requirements

An evidence package SHALL include:

- package and run IDs;
- goal, work item, and checkpoint;
- repository, branch, worktree, base, and exact head;
- environment identity;
- commands, timestamps, exit codes, stdout, and stderr;
- test totals and failing node IDs;
- failure classifications and baseline evidence;
- CI references;
- runtime and migration evidence when applicable;
- diff and artifact manifests;
- representation and hash scope;
- limitations and redactions;
- immutable preservation of failed and invalid attempts.

## 9. Branch and Worktree Closeout Evidence

Cleanup or pruning claims require:

- complete relevant inventory;
- no-prune remote fetch when remote state matters;
- dirty/untracked preservation;
- integration or patch-equivalence proof;
- target-specific dry-run previews;
- lock, storage, and process-use assessment;
- separate authorization for each destructive or pruning action;
- exact commands and outputs;
- cleanup, retention, or blocker receipt.

Absence of an item from a partial inventory is not proof that it does not exist.

## 10. Trust States

Assign trust to individual claims:

- `trusted`
- `partially_trusted`
- `untrusted`
- `not_evaluated`
- `conflicting`

Use claim classifications:

- `VERIFIED`
- `CLAIMED_NOT_VERIFIED`
- `ASSUMED`
- `UNKNOWN`
- `UNAVAILABLE`
- `NOT_APPLICABLE`

## 11. Fail-Closed Rules

Use `INSUFFICIENT EVIDENCE` or block the transition when:

- identity or source authority is unclear;
- evidence is stale or conflicts;
- exact test output is missing;
- the reviewed head changed;
- runtime behavior is claimed without runtime evidence;
- migration evidence is missing;
- representation scope is ambiguous;
- cleanup is proposed without inventory and preservation;
- production or risk conclusions exceed the evidence.

Failing closed does not assert a defect; it limits the conclusion.

## 12. Redaction and Sanitization

Evidence may be redacted for secrets, personal information, or sensitive
operations. Redaction SHALL preserve validation structure and record what was
redacted, why, and how the sanitized derivative relates to the source.

Never silently replace source evidence with a summary.

## 13. Evidence Anti-Patterns

Noncompliant behavior includes:

- using old CI after a new commit;
- claiming all tests passed without commands;
- hiding failures as unrelated without classification;
- using a Drive publication as repository truth;
- claiming a native document matches source bytes without proof;
- deleting failed runs;
- treating mergeability or publication as readiness;
- claiming branch cleanup from an incomplete inventory.


---

---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 05 — AEOS Review and Audit Standard

## 1. Purpose

This standard governs independent plan and architecture review, implementation
audit, corrective review, finding reconciliation, and merge-readiness review.
Its purpose is verification, not reassurance.

## 2. Independence and Identity

Consequential implementation and independent review SHALL use separate
contexts. The reviewer SHALL disclose any independence limitation.

Every review or audit SHALL identify:

- repository and authenticated remote;
- target branch, worktree, pull request, and artifact versions;
- base SHA and exact reviewed head SHA;
- governing objective, architecture, plan, and acceptance criteria;
- evidence reviewed and unavailable evidence;
- required checks and applicable test suites;
- review scope and exclusions.

A later commit changes the reviewed identity and invalidates current-head
approval until the new head is reviewed.

## 3. Plan and Architecture Review

A compliant review evaluates:

- objective and architecture alignment;
- scope completeness and out-of-scope preservation;
- repository-truth sufficiency;
- branch/worktree ownership and expected closeout;
- sequencing, dependencies, and stop conditions;
- security, authorization, concurrency, and idempotency;
- migration, compatibility, observability, rollback, and recovery;
- proportional test selection and failure disposition;
- evidence and representation requirements;
- post-merge validation and closeout planning.

Permitted dispositions:

- `APPROVE`
- `APPROVE WITH REQUIRED CHANGES`
- `REVISE`
- `REJECT`
- `INSUFFICIENT EVIDENCE`

Approval SHALL identify the reviewed artifact and exact repository identity.

## 4. Implementation Audit

An implementation audit SHALL inspect actual repository state and SHALL NOT
rely solely on an implementation report.

Required checks include:

- exact diff range and changed files;
- unauthorized or unrelated changes;
- architecture and acceptance-criteria conformance;
- tests, fixtures, assertions, exclusions, and failure classifications;
- applicable required-safe suites and CI checks;
- error handling, security, migrations, configuration, and compatibility;
- runtime behavior when runtime claims are made;
- evidence provenance, representation, and hash scope;
- documentation and residual risk.

Each acceptance criterion receives one of:

- `PASS`
- `PARTIAL`
- `FAIL`
- `NOT VERIFIED`
- `NOT APPLICABLE`

## 5. Findings

Each finding SHALL include:

- stable ID;
- severity;
- title and affected criterion;
- exact repository identity;
- evidence and impact;
- root cause or likely cause;
- required remediation;
- closure test;
- status, owner, and disposition history.

Permitted statuses:

- `OPEN`
- `FIX CLAIMED`
- `VERIFIED FIXED`
- `DEFERRED WITH ACCEPTED RISK`
- `REJECTED WITH RATIONALE`
- `NOT REPRODUCIBLE`

Findings SHALL NOT disappear. Only an independent review may mark a claimed fix
`VERIFIED FIXED`, and only the operator may accept risk.

## 6. Corrective Review

Corrective review SHALL:

- preserve original finding IDs and statements;
- inspect the corrected exact head;
- verify each claimed fix against its closure test;
- confirm proportional regression evidence;
- identify new regressions or scope drift;
- update every finding status explicitly;
- retain deferred, rejected, and not-authorized findings.

A corrected head different from the reviewed head requires a fresh review.

## 7. Audit Dispositions

Implementation audit may conclude:

- `PASS`
- `PASS WITH NON-BLOCKING FINDINGS`
- `FAIL — BLOCKERS REMAIN`
- `INSUFFICIENT EVIDENCE`

These are not merge authorization, deployment authorization, production
readiness, or risk acceptance.

## 8. Merge-Readiness Review

Merge-readiness review SHALL verify:

- exact candidate head and pull request;
- current-head independent review or audit;
- required checks;
- zero unresolved failures in applicable required-safe suites;
- no unresolved blocking findings;
- no unauthorized unrelated changes;
- clean or explicitly governed repository state;
- documented post-merge validation and closeout plan.

Permitted dispositions:

- `READY TO MERGE`
- `READY WITH REQUIRED CONDITIONS`
- `NOT READY`
- `INSUFFICIENT EVIDENCE`

A readiness disposition is not operator merge authorization.

## 9. Post-Merge and Closeout Review

A post-merge review SHALL identify the accepted target-branch commit and its
relationship to the reviewed candidate.

Closure review SHALL require:

- post-merge validation or explicit not-required decision;
- inventory and preservation evidence;
- integration, patch-equivalence, retention, or blocker proof;
- worktree, local branch, remote branch, metadata, and remote-ref dispositions;
- separate action authorizations;
- cleanup, retention, or blocker receipt.

A merge SHALL NOT be treated as closure.

## 10. Review Anti-Patterns

Noncompliant behavior includes:

- reviewing an unspecified or stale head;
- self-review presented as independent;
- summarizing without inspecting evidence;
- accepting tests without exact commands and identity;
- allowing blockers or failures to disappear;
- treating mergeability as readiness or readiness as authorization;
- verifying cleanup from an incomplete inventory;
- treating publication as approval.


---

---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 06 — AEOS Production Readiness Standard

## 1. Purpose

This standard separates readiness for merge, post-merge closure, deployment,
production use, and ongoing operation. A positive decision in one category does
not imply a positive decision in another.

## 2. Readiness Categories

1. Merge readiness.
2. Post-merge validation and cleanup/closure readiness.
3. Deployment readiness.
4. Production readiness.
5. Operational readiness.

## 3. Merge Readiness

Required evidence:

- approved scope and exact candidate head;
- current-head independent review or audit;
- required checks and proportional test evidence;
- zero unresolved failures in applicable required-safe suites;
- resolved blocking findings;
- no unauthorized unrelated changes;
- clean or explicitly governed repository state;
- documentation and closeout plan.

Blocking conditions include stale review, unresolved required-safe-suite
failures, blocking findings, ambiguous identity, unsafe migration, scope drift,
or missing core evidence.

Merge readiness does not authorize merge.

## 4. Merge Authorization

Only the operator may authorize merge. Authorization SHALL identify the exact
pull request and head and any required method or conditions.

A merge transitions work to `MERGED_PENDING_CLEANUP`. It does not authorize
cleanup, deployment, production activation, or closure.

## 5. Post-Merge Validation and Closure Readiness

Required evidence:

- accepted target-branch commit;
- relationship to the reviewed candidate;
- applicable post-merge checks or tests;
- documentation/index reconciliation;
- explicit not-required decisions where validation is omitted;
- inventory and preservation evidence;
- branch/worktree integration or retention proof;
- cleanup, retention, or blocker receipt.

Closure is blocked by unknown dirty state, unique unpreserved work, unverified
integration, ambiguous worktree/branch/ref disposition, or unauthorized
cleanup.

## 6. Deployment Readiness

Required evidence:

- deployable artifact or image identity;
- target environment;
- configuration and secret posture;
- migration and rollback plan;
- deployment procedure and authorization;
- health checks and observability;
- dependency and compatibility validation.

A merged or closed change is not automatically deployable.

## 7. Production Readiness

Required evidence:

- runtime validation of production-critical behavior;
- relevant integration and failure-mode tests;
- data-integrity and security checks;
- performance and capacity considerations;
- observability and user-impact assessment;
- rollback or forward-fix strategy;
- residual-risk disposition by the operator.

Blocking conditions include untested critical paths, missing authorization
checks, data-integrity uncertainty, unresolved High/Critical findings,
unobservable failure modes, or unaccepted material risk.

## 8. Operational Readiness

Required evidence:

- monitoring, logging, and alerting;
- runbooks and ownership;
- rollback or recovery procedures;
- known-issue tracking;
- watchpoints and post-deployment validation;
- support expectations and escalation path.

## 9. Decisions

For deployment, production, or operational readiness:

- `GO`
- `CONDITIONAL GO`
- `NO-GO`
- `INSUFFICIENT EVIDENCE`

For merge readiness:

- `READY TO MERGE`
- `READY WITH REQUIRED CONDITIONS`
- `NOT READY`
- `INSUFFICIENT EVIDENCE`

Every decision SHALL identify scope, exact identity, evidence, blockers,
conditions, approver, residual risk, and follow-up.

## 10. Risk Acceptance

Only an authorized human may accept risk. The record SHALL identify the risk,
impact, mitigation or deferral, scope, duration when applicable, approver, and
timestamp.

AI systems SHALL NOT infer risk acceptance from merge, publication, review, or
tool access.

## 11. Readiness Anti-Patterns

Noncompliant behavior includes:

- treating mergeability as merge readiness;
- treating merge readiness as merge authorization;
- treating merge as cleanup, deployment, or closure;
- treating cleanup as deployment readiness;
- issuing GO from unit tests alone;
- omitting rollback or runtime validation;
- accepting unresolved failures without evidence and authority;
- combining readiness categories into one ambiguous disposition.


---

---
standard: AEOS
version: "1.2"
status: normative
license: internal-use
---

# 07 — AEOS Local Agent Operating Contract

## 1. Purpose

This contract governs implementation-capable local and repository agents,
including Claude Code, Codex, Grok, Composer, IDE agents, and equivalent
approved harnesses. The agent implements authorized scope, collects evidence,
and reports state. It is not the operator, independent reviewer, merge authority,
deployment authority, or risk authority.

## 2. Mandatory Preflight

Before substantive editing, report and verify:

- repository path and authenticated remote;
- default branch;
- registered branch identity;
- registered worktree identity, mode, and path;
- base SHA, exact head SHA, merge base, and upstream;
- pull request when applicable;
- dirty and untracked state;
- active goal, work item, state, and checkpoint;
- authorization identifier and exact permitted action;
- governing sources and acceptance criteria;
- planned files and proportional validation;
- prohibited actions and stop conditions.

A non-canonical branch or worktree SHALL be registered before editing. A dirty
or identity-mismatched worktree fails closed unless the exact authorization
states how pre-existing material is preserved and handled. Do not absorb
unrelated dirty changes into authorized work.

## 3. Scope and Architecture

Implement only authorized scope. Preserve approved architecture, constraints,
and acceptance criteria. Report repository conflicts before proceeding.

Without authorization, do not introduce dependencies, change public interfaces,
remove safeguards, alter unrelated tests, perform broad refactors, or hide scope
expansion as cleanup.

## 4. Git and Lifecycle Safety

Without explicit operator authorization, do not:

- push, merge, force-push, or rewrite history;
- rebase a shared branch;
- reset hard or run broad destructive clean;
- remove a worktree;
- delete a local or remote branch;
- prune worktree metadata or remote references;
- delete tags, data, or evidence;
- deploy, activate production, mutate secrets, or run irreversible migrations;
- accept risk or activate the next lifecycle state.

These are separate governed actions:

1. worktree removal;
2. local branch deletion;
3. remote branch deletion;
4. worktree metadata pruning;
5. remote-reference pruning.

Authorization for one does not authorize another.

## 5. Preservation Before Cleanup

Before cleanup, deletion, or pruning:

- inventory branches, worktrees, refs, tags, dirty state, locks, and process
  dependencies;
- perform no-prune fetch when remote state matters;
- preserve unique, dirty, inaccessible, uncertain, or process-dependent material;
- prove integration, patch equivalence, retention need, or blocker;
- preview the exact target action;
- obtain target-specific authorization.

Uncertainty fails closed to preservation. `git reset --hard`, broad `git clean`,
forced worktree removal, and `git branch -D` are not routine hygiene tools.

## 6. Implementation Behavior

Prefer small reviewable changes, tests near changed behavior, coherent commits
when committing is authorized, minimal formatting churn, compatibility, and
explicit deviation reporting.

Stop before proceeding when architecture, scope, migration behavior, side
effects, acceptance criteria, environment, or test infrastructure differs
materially from the approved contract.

## 7. Test-Selection Authority and Precedence

Testing is governed jointly by the exact work-item authorization and:

```text
.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md
```

A handoff-specified test is binding only when mapped to an acceptance criterion,
changed behavior or dependency, changed shared infrastructure, a named
regression risk, or an exact merge/release gate. The handoff must state that
mapping or incorporate an approved plan that does.

Do not silently omit a mapped required test. Do not silently run an unmapped
broad suite merely because a generic template or prior handoff lists it.

When a handoff test mandate conflicts with Standard 11, stop and report a
deviation containing the exact mandate, missing or conflicting mapping,
proposed bounded test set, affected acceptance criteria, and requested authority.
Only an exact later operator decision or higher-authority repository source may
resolve the conflict. An agent assertion cannot narrow an acceptance criterion,
safeguard, or gate.

The canonical merge-safe repository command is:

```bash
bash scripts/test-safe.sh
```

Unfiltered `pytest`, custom marker overrides, or selected targets are not the
canonical merge-safe gate.

## 8. Test Evidence and Failure Disposition

Test reporting SHALL include command, selected targets, selection rationale,
environment, dependency/configuration identity, exact head, full result, failing
IDs, exclusions, baseline evidence, evidence reuse, and gates not run with
reasons.

Every observed failure SHALL be preserved and receive a durable disposition
under `docs/governance/test-failure-triage.md` before the affected checkpoint
advances. Creating a triage record is not corrective authority.

A separate corrective agent requires separate operator authorization, isolated
branch/worktree ownership, non-overlapping scope, evidence, and independent
review. The integrated candidate remains blocked until applicable required-safe
suites are green.

## 9. Evidence Requirements

Produce evidence containing:

- exact repository and environment identity;
- changed files and diff scope;
- acceptance-criteria matrix;
- commands, exit codes, and outputs;
- tests and failure classifications;
- runtime or migration evidence when applicable;
- artifact representation, MIME type, hash scope, and hash when material;
- deviations, known issues, and unavailable evidence;
- final repository status.

An implementation report is a claim index, not independent proof.

## 10. Post-Merge Closeout

Merge moves work to `MERGED_PENDING_CLEANUP`. It does not authorize further
action or close the goal.

Before closure, produce or reference:

- accepted merge identity;
- post-merge validation or explicit not-required decision;
- preservation and integration proof;
- worktree, local branch, remote branch, metadata, and remote-ref disposition;
- cleanup, retention, or blocker receipt.

Only then may an authorized transition move the work to `CLOSED`.

## 11. Stop Conditions

Stop when:

- authorization is absent, stale, mismatched, or exceeded;
- repository drift invalidates authorization or review;
- dirty state lacks disposition;
- scope or architecture must change;
- a consequential action is required;
- a failure relationship is unknown;
- a required suite cannot run;
- evidence cannot support the requested claim;
- retry limits are exhausted;
- sensitive information may be exposed;
- parallel correction overlaps a shared surface;
- required-safe-suite failures remain unresolved;
- cleanup evidence or authority is incomplete.

## 12. Final Report

The final report SHALL include:

1. bounded disposition;
2. repository, branch, worktree, base, and exact head;
3. authorization and work item;
4. commits and changed files;
5. implementation summary;
6. acceptance-criteria matrix;
7. tests and exact outcomes;
8. failure dispositions;
9. evidence and representation details;
10. deviations and known issues;
11. unverified areas;
12. final git status;
13. lifecycle state;
14. recommended next gate.

The agent SHALL NOT declare independent approval, merge authorization,
production readiness, cleanup completion, or risk acceptance unless explicitly
performing the separately authorized decision workflow.


---

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


---

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


---

---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 10 — AEOS Prompt Entry Points

These prompts initiate a governed mode. They do not replace repository policy,
the Master Index, or explicit authorization.

## Discovery / Repository Truth

```text
Mode: Discovery / Repository Truth
Repository / authenticated remote:
Issue or goal:
Branch / worktree:
Base SHA / expected head:
Objective:

Authenticate repository and GitHub state. Record branch, worktree, base and
exact head, PR/checks when present, dirty state, relevant files, tests,
schemas, migrations, runtime surfaces, verified facts, assumptions, unknowns,
and evidence gaps. When branch/worktree hygiene is material, inventory refs,
tags, locks, and process dependencies without pruning or deleting. Do not
design or implement. Produce a repository-truth report and bounded next gate.
```

## Architecture

```text
Mode: Architecture
Approved objective:
Repository-truth report:
Exact repository identity:
Constraints:

Develop the target architecture. Include components, interfaces, data and trust
boundaries, authorization, failure behavior, observability, alternatives,
invariants, risks, acceptance criteria, and repository-specific lifecycle
implications. Do not begin implementation planning until the architecture is
complete and independently reviewed when required.
```

## Implementation Planning

```text
Mode: Implementation Planning
Approved architecture:
Acceptance criteria:
Repository / branch / worktree / base head:
Authorization:

Produce an executable plan with bounded work packages, branch/worktree
ownership, expected closeout disposition, files/symbols, proportional tests,
failure classification, integrated-green requirements, evidence representation
and hash scope, rollback, prohibited actions, stop conditions, independent
review gates, post-merge validation, and cleanup/retention/blocker requirements.
Do not implement.
```

## Local Agent Handoff

```text
You are the local agent for one authorized AEOS work package.

Before editing, authenticate repository/remote, registered branch and worktree,
base SHA, exact head, PR, dirty state, active work item, authorization, scope,
and prohibited actions.

Implement only the approved package. Use proportional testing and preserve every
failure for classification. Do not redesign, expand scope, weaken tests, push,
merge, reset hard, clean broadly, remove worktrees, delete branches, prune refs,
deploy, modify secrets, run irreversible migrations, accept risk, or activate
the next state without exact operator authorization.

Objective:
Scope:
Out of scope:
Acceptance criteria:
Required tests:
Required evidence:
Retry limit:
Stop conditions:
Final report:
```

## Plan or Architecture Review

```text
Mode: Independent Plan Review
Reviewed artifact/version:
Repository base and exact head:
Reviewer context:

Evaluate objective alignment, architecture, scope, branch/worktree ownership,
sequencing, security, migration, rollback, proportional tests, evidence,
post-merge validation, and closeout. Bind the review to the exact artifact and
head. Return APPROVE, APPROVE WITH REQUIRED CHANGES, REVISE, REJECT, or
INSUFFICIENT EVIDENCE. State that a later commit invalidates current-head
approval.
```

## Implementation Audit

```text
Mode: Independent Implementation Audit
Repository / PR / base / exact head:
Approved plan and acceptance criteria:
Evidence package:

Inspect actual diff and evidence. Verify test selection, failures, security,
migrations, runtime claims, documentation, representation/hash scope, and
repository identity. Produce an acceptance matrix, stable findings, evidence
assessment, and PASS, PASS WITH NON-BLOCKING FINDINGS, FAIL — BLOCKERS REMAIN,
or INSUFFICIENT EVIDENCE. Do not repair implementation.
```

## Corrective Review

```text
Mode: Independent Corrective Review
Original findings:
Corrected exact head:
Corrective evidence:

Preserve every finding ID and history. Verify each claimed fix against its
closure test at the corrected exact head. Retain deferred, rejected, and
not-authorized findings. Only independent review may set VERIFIED FIXED. A later
commit invalidates the review.
```

## Merge Readiness

```text
Mode: Merge Readiness
Pull request / exact candidate head:
Required checks and safe suites:
Current-head review:

Verify current-head review, required checks, zero unresolved failures in
applicable required-safe suites, no blocking findings, no unauthorized changes,
and a post-merge validation/closeout plan. Return READY TO MERGE, READY WITH
REQUIRED CONDITIONS, NOT READY, or INSUFFICIENT EVIDENCE. Do not merge and do
not imply operator authorization.
```

## Post-Merge Validation

```text
Mode: Post-Merge Validation
Reviewed candidate:
Accepted target-branch commit:
Merge receipt:

Verify the accepted identity and relationship to the reviewed candidate. Run or
inspect required post-merge checks, reconcile documentation/indexes, identify
runtime validation needs, and record explicit not-required decisions. Do not
perform cleanup without separate authorization.
```

## Branch and Worktree Closeout

```text
Mode: Branch and Worktree Closeout
Merged work item:
Accepted merge identity:
Registered branch/worktree records:
Authorized closeout actions:

Inventory branches, worktrees, refs, tags, dirty state, locks, and process use.
Perform no-prune fetch when remote state matters. Preserve unique or uncertain
material and prove integration, patch equivalence, retention need, or blocker.
Preview each target action. Treat worktree removal, local branch deletion,
remote branch deletion, metadata pruning, and remote-ref pruning as separate
authorizations. Produce a cleanup, retention, or blocker receipt. Do not move to
CLOSED without the required evidence.
```

## Deployment / Production Readiness

```text
Mode: Readiness Review
Exact artifact and environment:
Requested category:

Evaluate deployment, production, and operational readiness separately from
merge and cleanup. Verify artifact identity, configuration, migrations,
rollback, runtime behavior, observability, security, data integrity, support,
and residual risk. Return GO, CONDITIONAL GO, NO-GO, or INSUFFICIENT EVIDENCE
for only the authorized category. Only the operator may accept risk or authorize
deployment.
```

## Pattern / Corpus Review

```text
Mode: Pattern / Corpus Review
Observation and evidence:

Determine whether the practice is a positive pattern, negative pattern, or
candidate. Identify exact evidence, context, applicability, non-applicability,
consequences, and classification: AEOS Core, Optional Profile, Reference
Implementation Only, Do Not Generalize, or Needs More Evidence.
```


---

---
standard: AEOS
version: "1.2"
status: normative
license: internal-use
---

# 11 — Repository Test Selection and Failure Disposition Standard

## 1. Purpose

This standard defines proportional, evidence-oriented test selection and durable
disposition of every observed test failure for
`RMF112018/hb-personal-assistant`. It prevents both under-testing and repeated
execution of expensive suites that add no material assurance to the active
change.

It does not weaken acceptance criteria, safeguards, or merge/release gates. It
separates edit ownership from the requirement that the integrated candidate
ultimately satisfy every applicable gate.

## 2. Mandatory suite mapping

Every mandatory test or validation command SHALL map to at least one of:

1. an explicit acceptance criterion;
2. changed behavior;
3. a direct or demonstrated transitive dependency;
4. a changed shared-infrastructure surface;
5. a named regression risk;
6. an exact merge, release, deployment, or production-readiness gate.

A suite SHALL NOT become mandatory solely because an earlier work item ran it, a
generic template lists it, or an agent has historically run it. A mapped test in
an approved authorization remains binding unless an exact higher-authority or
later operator decision supersedes it. Conflicts follow Standard 07 §7 and fail
closed to a deviation report.

## 3. Execution stages

### 3.1 Inner loop

After a small edit, run the smallest test that can falsify the current claim: a
failing node ID, one class or file, or a narrow changed-module syntax, lint,
type, or import check. Do not run broad domain bundles, unrelated canaries, or
the merge-safe suite after every edit or conversational turn.

### 3.2 Coherent slice

After a coherent implementation slice, run directly affected tests, direct
caller/consumer seams, changed-file static checks, and required adversarial or
invariant tests.

### 3.3 Candidate validation

Before creating or updating a review candidate, run the complete bounded
work-item acceptance suite defined by the approved plan or authorization, as
modified only by a later exact decision.

### 3.4 Committed-SHA checkpoint

At the final committed SHA, capture the work-item suite, static checks, baseline
comparison, triggered canaries, command, environment, dependency/configuration
identity, result, and evidence hash. A costly suite normally runs once per
materially different candidate SHA, not once per agent turn.

### 3.5 Merge and release validation

The canonical merge-safe repository gate is:

```bash
bash scripts/test-safe.sh
```

It runs the full safe Python scope `tests/` with markers `integration`, `manual`,
and `live` excluded, followed by the frontend Vitest suite. It fails if required
frontend dependencies are unavailable. `bash scripts/test-safe.sh --collect-only`
validates Python collection and intentionally does not claim frontend execution.
`--python-only` and `--frontend-only` are diagnostic component runs and do not
individually satisfy the full gate.

Unfiltered `pytest` is permitted only under an exact authorization that accepts
the external/manual/live effects and required environment. Selected targets,
marker overrides, or arbitrary pytest arguments are prohibited through the
canonical script because they would no longer represent the merge-safe suite.

Run the full safe gate for merge or release readiness, broad cross-domain
refactors, global fixtures or discovery, dependency or packaging changes,
runtime bootstrap, or behavior reasonably capable of affecting unrelated
areas. Focused acceptance evidence does not replace an applicable merge gate,
and a full gate does not replace focused acceptance evidence.

Merge readiness requires zero unresolved failures in every applicable required
suite.

## 4. Impact classes

| Class | Typical surface | Validation |
|---|---|---|
| Local | One isolated function, module, or policy | Targeted tests and changed-file checks |
| Domain | Multiple files in one bounded domain | Domain suite and direct integration seams |
| Shared infrastructure | Migrator, schema/bootstrap, common DB, packaging, global fixtures | Affected domains and demonstrated canaries |
| Cross-domain | Shared API, CLI, contract, or refactor | All affected domains and broader selected regression tests |
| Merge/release | Integrated candidate | `bash scripts/test-safe.sh` plus gate-specific evidence |

## 5. Forecasting and schedule bundles

Run `scripts/test-forecasting.sh` for forecast generation, configuration, read
models, semantic/readiness gates, forecast API/UI, forecast-related financial
normalization, or demonstrated shared dependencies.

Run `scripts/test-schedule.sh` for schedule ingestion, XER/XML/MSP parsing,
quality, CPM/critical path, mapping, projection, migration, or demonstrated
shared dependencies.

The schedule bundle is a cross-domain canary for
`src/hb_assistant/store/migrator.py`, shared schema/bootstrap behavior, or other
verified common database infrastructure. It is not a default canary for isolated
source-index repository, connector, model, or service changes. Run both bundles
only when both domains or shared infrastructure used by both are affected.

## 6. Failure classification

Every failing test SHALL be preserved and classified:

| Classification | Required disposition |
|---|---|
| Candidate regression | Stop the affected checkpoint and correct within the active work item |
| Reproducible pre-existing product defect | Preserve base/candidate evidence and request separate corrective authorization |
| Invalid or stale test | Request bounded test-correction work; do not weaken, delete, or skip without evidence and review |
| Flaky or nondeterministic test | Preserve repeated-run evidence and request stabilization work |
| Environment or configuration failure | Correct or formally document the environment; do not report product green |
| Relationship unknown | Treat as potentially related and stop the affected checkpoint |

A failure is not unrelated because its filename or domain differs. Pre-existing
status requires reproduction on the immutable base SHA under a materially
equivalent command, dependencies, environment, fixtures, and inputs, or
equivalent direct causal evidence.

## 7. Durable failure identity and ownership

Every observed failure SHALL immediately receive a durable record under
`docs/governance/test-failure-triage.md`. The preferred GitHub issue template is
`.github/ISSUE_TEMPLATE/test-failure.yml`, with stable identity
`TF-<issue-number>`.

The record must contain discovery time and source work item, exact failing IDs,
triage owner, classification state, base/candidate evidence, affected criterion
or gate, disposition, authorization state, corrective identity when authorized,
independent review, integrated-candidate result, and closure evidence.

The initial classification is `RELATIONSHIP_UNKNOWN` unless direct evidence
supports another state. Corrective authorization starts as
`AWAITING_AUTHORIZATION` unless an exact authorization already exists. A known
failure may remain outside the primary work item's edit scope, but it may not be
unowned, untracked, or treated as green.

## 8. Parallel corrective work

A separate corrective agent MAY work in parallel only when all are true:

1. base-SHA reproduction proves the failure pre-existing;
2. current acceptance evidence remains valid;
3. the corrective file/test surface is bounded;
4. edit and evidence ownership do not overlap;
5. no shared schema, migrator/bootstrap, global fixture, discovery,
   dependency/configuration, security control, or common surface is involved;
6. a separate branch and, when local, worktree are registered;
7. a separate explicit authorization, evidence package, and independent review
   exist;
8. integration is separately authorized;
9. the combined candidate reruns every applicable checkpoint and merge gate.

The primary agent may create the triage record and request authorization, but
shall not create or activate the corrective agent on its own authority. Unknown
or overlapping relationships block the affected checkpoint.

## 9. No-known-failure integration rule

Focused implementation may continue only within the controls above. No
integrated candidate is merge-ready while an applicable required test has an
unexplained or unresolved failure. This requires zero unexplained failures,
zero untracked pre-existing failures, zero required-gate failures, and zero
waivers based only on age or apparent domain distance.

## 10. Evidence reuse

Evidence MAY be reused only when the tested SHA, command/targets,
dependency/configuration identity, interpreter/material environment, fixtures or
external inputs, and evidence purpose are unchanged and recorded. Do not rerun
an identical suite for a bookkeeping-only turn. Rerun when any identity changes
in a way capable of affecting the result. Declare parent-baseline reuse in the
evidence manifest.

## 11. Plan and authorization requirements

Plans and authorizations SHALL distinguish inner-loop tests, candidate tests,
committed-checkpoint tests, conditional canaries with triggers, merge/release
tests, failure-classification evidence, durable failure ownership, parallel work
when authorized, and final integrated-green requirements. Each required suite
shall include its criterion, dependency, risk, or gate mapping.

Approved historical plans are not silently rewritten. Use a superseding plan or
an exact operator decision.

## 12. Stop conditions

Stop and report when plan and standard conflict without a superseding decision,
blast-radius evidence is unavailable for high-risk change, a required suite
cannot execute, narrowing would weaken a criterion or safeguard, a failure is
not proven pre-existing, parallel work overlaps, or the combined candidate
remains red.

## 13. Reporting

Reports SHALL state tests and exact results, selection mappings, required tests
not run, every failure identity/classification and evidence, triage and
corrective identities, reused evidence, deferred broader gates, integrated-green
status, and residual unverified areas.
