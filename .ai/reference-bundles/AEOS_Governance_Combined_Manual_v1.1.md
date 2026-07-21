# AEOS Governance Combined Reference Manual v1.1

**Status:** Non-canonical convenience bundle  
**Generated for:** GitHub-first governance synchronization based on PR #319  
**Canonical source set:** `.ai/project-sources/00_AEOS_MASTER_INDEX.md` through `.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md`

This bundle is a compact cross-standard reference. The individual files under
`.ai/project-sources/` are normative and override this bundle when wording or
version differs.

## Governing Model

AEOS separates factual truth from action authority:

1. authenticated runtime evidence governs deployed behavior;
2. authenticated repository and GitHub state governs engineering identity and
   lifecycle;
3. repository-local governance, accepted ADRs, approved specifications, and
   acceptance criteria govern repository-specific expectations;
4. AEOS standards govern generic planning, execution, review, and assurance;
5. approved publication/reference governance governs publication identity;
6. prior chats and agent reports are claim indexes;
7. model memory is lowest authority.

The current operator instruction defines task intent and permitted scope. Only
the operator may authorize consequential state transitions, merge, cleanup,
deployment, production activation, or risk acceptance.

## Repository-Specific GitHub-First Control Plane

For `RMF112018/hb-personal-assistant`:

- repository and GitHub are canonical for active engineering state;
- runtime evidence is canonical for deployed behavior;
- Google Drive is publication/reference and may not maintain a competing
  active-state ledger;
- ADR-019 and `POL-GIT-HYGIENE-001` govern branch/worktree lifecycle;
- independent review binds to the exact reviewed head;
- a later commit invalidates current-head approval;
- merge transitions work to `MERGED_PENDING_CLEANUP`;
- post-merge validation and a cleanup, retention, or blocker receipt are
  required before closure;
- Phase B, cleanup, deployment, production activation, and risk acceptance
  remain separately authorized actions.

## Standard Catalogue

### 00 — Master Index v1.2

Routes operating modes to governing sources and required artifacts. Requires
exact repository identity preflight, separates truth precedence from action
authority, and includes merge-readiness, post-merge-validation, closeout,
evidence-packaging, and finding-reconciliation routes.

### 01 — Operating Manual v1.1

Defines evidence-first behavior, operator authority, GitHub-first execution
state, exact-head binding, branch/worktree registration, representation-aware
evidence, and distinct review/readiness dispositions.

### 02 — Workflow Standard v1.1

Normative lifecycle:

```text
Intake
→ Discovery / Repository Truth
→ Architecture, when required
→ Implementation Planning
→ Independent Plan Review
→ Authorized Implementation
→ Evidence Packaging
→ Independent Audit
→ Corrective Implementation / Audit, when required
→ Merge Readiness
→ Explicit Merge Authorization
→ Merge
→ Post-Merge Validation
→ Branch and Worktree Cleanup, Retention, or Blocker Receipt
→ Bounded Closure
→ Separately Authorized Deployment and Production Lifecycle
```

### 03 — Artifact Standard v1.1

Requires stable artifact, repository, work-item, authorization, branch,
worktree, SHA, PR, review, lifecycle, evidence, representation, and publication
identity. Defines merge-readiness, post-merge-validation, and closeout receipts.

### 04 — Evidence and Trust Standard v1.1

Evidence must be specific, reproducible, relevant, current, identity-bound, and
representation-aware. Valid hash scopes are `stored_raw_bytes`, `source_bytes`,
`exported_bytes`, and `not_applicable`. Cross-representation equivalence is
prohibited.

### 05 — Review and Audit Standard v1.1

Independent reviews identify exact artifact and repository identities. Later
commits invalidate current-head approval. Findings remain stable until explicit
disposition. Merge-readiness review is distinct from operator merge
authorization.

### 06 — Production Readiness Standard v1.1

Separates merge readiness, post-merge cleanup/closure readiness, deployment
readiness, production readiness, and operational readiness. A positive decision
in one category does not imply another.

### 07 — Local Agent Operating Contract v1.1

Requires registered branch/worktree identity, bounded scope, proportional
tests, preserved failures, evidence, and safe stop behavior. Inventory,
no-prune fetch, preservation, integration proof, preview, and exact authority
precede cleanup or pruning.

### 08 — Vocabulary and Taxonomy v1.1

Defines repository/runtime/publication truth, action authority, exact head,
reviewed head, repository drift, branch/worktree identity, lifecycle states,
representation, hash scope, and cleanup/retention/blocker receipts.

### 09 — Pattern Language v1.1

Adds Exact-Identity Review Binding, Preservation Before Pruning,
Merge-to-Closeout Lifecycle, and Representation-Scoped Integrity patterns, plus
corresponding anti-patterns.

### 10 — Prompt Entry Points v1.1

Provides bounded prompts for discovery, architecture, implementation planning,
local execution, independent review/audit, corrective review, merge readiness,
post-merge validation, branch/worktree closeout, readiness, and corpus review.

### 11 — Repository Test Selection and Failure Disposition

Requires proportional test selection based on risk, explicit suite-to-risk
mapping, preservation and classification of every failure, separately
authorized isolated corrective streams, and zero unresolved failures in
applicable required-safe suites before integration.

## Canonical Goal/Skill Contract

The eight canonical skills remain:

1. `aeos-goal-controller`
2. `aeos-repository-truth`
3. `aeos-checkpoint-manager`
4. `aeos-implementation-planner`
5. `aeos-work-package-executor`
6. `aeos-evidence-packager`
7. `aeos-independent-auditor`
8. `aeos-finding-reconciler`

All skills use `.ai/agent-skills/_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`.
They may execute only the currently authorized state and must stop at the next
review or operator gate.

## Goal Lifecycle Vocabulary

```text
GOVERNANCE_INITIALIZATION
REPOSITORY_TRUTH
ARCHITECTURE
IMPLEMENTATION_PLANNING
PLAN_EXTERNAL_REVIEW
IMPLEMENTATION
IMPLEMENTATION_EXTERNAL_AUDIT
CORRECTIVE_IMPLEMENTATION
CORRECTIVE_EXTERNAL_AUDIT
MERGE_READINESS
MERGE_AUTHORIZATION
MERGED_PENDING_CLEANUP
POST_MERGE_VALIDATION
BRANCH_WORKTREE_CLOSEOUT
BOUNDED_CLOSURE_ASSESSMENT
CLOSED
```

`MERGED_PENDING_CLEANUP` must not transition directly to `CLOSED`.

## Representation and Publication Boundary

A native Google Doc has stable Drive identity and revision history but no
portable raw-byte SHA-256. Source, raw stored file, native object, and export are
distinct representation classes. Publication success does not establish
technical correctness, review approval, engineering lifecycle state, or action
authority.

## Validation

The canonical package validators enforce:

- eight canonical skills;
- required shared resources;
- exact-head and closeout contract terms;
- recursive rejection of `.DS_Store`, `._*`, and `__MACOSX`;
- rejection of prohibited legacy schemas;
- byte identity of paired root/shared goal-loop templates and schemas;
- required GitHub-first policy pointers;
- manifest schema/version and mandatory rules;
- valid JSON;
- current `.ai/CHECKSUMS.txt`.

This reference bundle is not an authorization, review, readiness decision, or
replacement for repository truth.
