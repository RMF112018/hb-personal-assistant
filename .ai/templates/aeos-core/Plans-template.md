---
title: "{{title}}"
artifact_id: "PLAN-{{id}}"
classification: "Plans"
artifact_type: "Implementation Plan"
version: "0.1"
status: "Draft"
date_created: "{{date:YYYY-MM-DD}}"
date_updated: "{{date:YYYY-MM-DD}}"
owner: "{{owner}}"
author: "{{author}}"
repository: "{{repository}}"
target_branch: "{{target_branch}}"
approved_architecture: "{{approved_architecture}}"
related_features: []
related_adrs: []
related_reviews: []
evidence_references: []
tags:
  - aeos
  - plan
  - implementation
---

# {{title}}

**Classification:** Plans
**Artifact Type:** Implementation Plan
**Version:** 0.1
**Status:** Draft

## Objective

-

## Current State

### Verified Facts

-

### Assumptions

-

### Inferences

-

### Unknowns

-

## Desired End State

-

## Scope

### In Scope

-

### Out of Scope

-

## Constraints and Invariants

-

## Dependencies

-

## Risks

| Risk ID | Severity | Description | Mitigation | Stop Condition |
|---|---|---|---|---|
| `RISK-...` |  |  |  |  |

## Repository Preflight

Require:

- repository path;
- current branch;
- HEAD SHA;
- base SHA;
- worktree state;
- relevant files inspected;
- runtime or toolchain environment;
- blockers or conflicts.

## Implementation Phases

### Phase 1 — {{phase_name}}

**Objective:**
**Expected files/components:**
**Steps:**

1.
2.
3.

**Tests:**
**Evidence:**
**Exit criteria:**
**Stop conditions:**

### Phase 2 — {{phase_name}}

**Objective:**
**Expected files/components:**
**Steps:**

1.
2.
3.

**Tests:**
**Evidence:**
**Exit criteria:**
**Stop conditions:**

## Test Strategy

| Layer | Scope | Command / Method | Required Evidence |
|---|---|---|---|
| Unit |  |  |  |
| Integration |  |  |  |
| Runtime |  |  |  |
| Regression |  |  |  |
| Failure Injection |  |  |  |

## Acceptance Criteria

| ID | Criterion | Implementation Evidence | Test Evidence |
|---|---|---|---|
| `AC-...` |  |  |  |

## Evidence Requirements

- exact commands;
- complete outputs;
- base and head SHAs;
- changed-file list;
- diff;
- runtime or migration output;
- baseline comparison;
- known limitations;
- final Git status.

## Rollback or Forward-Recovery Strategy

-

## Forbidden Actions

- force push;
- destructive reset;
- unrelated deletion;
- merge;
- deployment;
- irreversible migration;
- secret mutation;
- unapproved scope expansion.

## Stop Conditions

-

## Required Final Implementation Report

1. Disposition
2. Repository state
3. Base and head SHAs
4. Commits created
5. Files changed
6. Implementation summary
7. Architecture conformance or deviations
8. Acceptance-criteria matrix
9. Tests executed with exact results
10. Runtime or migration evidence
11. Compatibility and security impact
12. Deviations
13. Known issues
14. Unverified areas
15. Final Git status
16. Rollback posture
17. Recommended next gate

## Recommended Next Gate

- Plan Review / Implementation / Evidence Collection / Other


---

## Document Control

| Field | Value |
|---|---|
| Artifact ID | `{{artifact_id}}` |
| Classification | `Plans` |
| Artifact Type | `Implementation Plan` |
| Version | `0.1` |
| Status | `Draft` |
| Owner | `{{owner}}` |
| Author | `{{author}}` |
| Created | `{{date:YYYY-MM-DD}}` |
| Last Updated | `{{date:YYYY-MM-DD}}` |
| Repository / Workspace | `{{repository_or_workspace}}` |
| Branch / PR / Commit | `{{branch_pr_commit}}` |
| Supersedes | `{{supersedes}}` |
| Superseded By | `{{superseded_by}}` |

## Related Artifacts

- Governing sources: `{{governing_sources}}`
- Related ADRs: `{{related_adrs}}`
- Related architecture: `{{related_architecture}}`
- Related features: `{{related_features}}`
- Related plans: `{{related_plans}}`
- Related reviews: `{{related_reviews}}`
- Related audits: `{{related_audits}}`
- Related decisions: `{{related_decisions}}`

## Evidence and Traceability

- Evidence references: `{{evidence_references}}`
- Evidence package: `{{evidence_package}}`
- Acceptance criteria: `{{acceptance_criteria_refs}}`
- Findings: `{{finding_refs}}`
- Risks: `{{risk_refs}}`
- Source repository: `{{source_repository}}`
- Source SHA or version: `{{source_sha_or_version}}`

## Change Log

| Version | Date | Author | Change Summary |
|---|---|---|---|
| `0.1` | `{{date:YYYY-MM-DD}}` | `{{author}}` | Initial version |

## Review and Approval

| Role | Name | Decision / Status | Date | Notes |
|---|---|---|---|---|
| Author | `{{author}}` | Drafted | `{{date:YYYY-MM-DD}}` |  |
| Reviewer | `{{reviewer}}` | `{{review_status}}` | `{{review_date}}` |  |
| Approver | `{{approver}}` | `{{approval_status}}` | `{{approval_date}}` |  |

## Final Disposition

**Disposition:** `{{disposition}}`

**Next Gate:** `{{next_gate}}`

**Residual Risks / Open Items:**

-

> End of governed artifact.
