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
