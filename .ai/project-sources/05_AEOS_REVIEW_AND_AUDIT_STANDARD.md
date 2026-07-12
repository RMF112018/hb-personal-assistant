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
