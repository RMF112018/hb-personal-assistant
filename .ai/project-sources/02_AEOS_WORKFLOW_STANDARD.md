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
