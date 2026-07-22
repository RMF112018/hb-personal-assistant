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
