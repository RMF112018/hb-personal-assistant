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
