---
title: "{{title}}"
artifact_id: "AUDIT-{{id}}"
classification: "Audits"
artifact_type: "Audit Report"
version: "0.1"
status: "Draft"
date_created: "{{date:YYYY-MM-DD}}"
date_updated: "{{date:YYYY-MM-DD}}"
audit_type: "{{audit_type}}"
auditor: "{{auditor}}"
repository: "{{repository}}"
target_branch_pr_commit: "{{target_branch_pr_commit}}"
objective: "{{objective}}"
baseline_sha: "{{baseline_sha}}"
head_sha: "{{head_sha}}"
governing_sources: []
acceptance_criteria_refs: []
evidence_references: []
tags:
  - aeos
  - audit
  - evidence
---

# {{title}}

**Classification:** Audits
**Artifact Type:** Audit Report
**Version:** 0.1
**Status:** Draft

## Audit Conclusion

State the audit disposition first.

## Audit Type

Repository-Truth Audit / Implementation Audit / Evidence Audit / Security Audit / Conformance Audit / Other

## Audit Scope

-

## Target

- Repository:
- Branch / PR / Commit:
- Baseline SHA:
- Head SHA:
- Worktree state:
- Objective:

## Governing Sources

-

## Evidence Reviewed

| Evidence ID | Source | Description | Trust State | Limitation |
|---|---|---|---|---|
|  |  |  | Trusted / Partial / Untrusted / Not Evaluated |  |

## Access Limitations

-

## Verified Facts

-

## Claims Requiring Verification

-

## Repository and Diff Assessment

-

## Architecture-Conformance Assessment

-

## Acceptance-Criteria Matrix

| ID | Expected Behavior | Implementation Evidence | Test Evidence | Status | Notes |
|---|---|---|---|---|---|
| `AC-...` |  |  |  | PASS / PARTIAL / FAIL / NOT VERIFIED / NOT APPLICABLE |  |

## Test-Evidence Assessment

- Commands:
- Environment:
- Results:
- Baseline comparison:
- Coverage limitations:

## Security and Trust-Boundary Assessment

-

## Migration and Data-Integrity Assessment

-

## Compatibility and Rollback Assessment

-

## Runtime and Operational Assessment

-

## Finding Ledger

| Finding ID | Severity | Title | Evidence | Impact | Required Remediation | Verification Method | Status |
|---|---|---|---|---|---|---|---|
| `FIND-...` | Critical / High / Medium / Low / Informational |  |  |  |  |  | Open |

## Evidence Gaps

-

## Required Corrective Actions

| Action ID | Finding(s) | Required Action | Evidence Required | Blocking |
|---|---|---|---|---|
| `CA-...` |  |  |  | Yes / No |

## Readiness Separation

| Category | Disposition | Basis |
|---|---|---|
| Merge readiness |  |  |
| Deployment readiness |  |  |
| Production readiness |  |  |
| Operational readiness |  |  |

## Audit Disposition

Select one:

- `PASS`
- `PASS WITH NON-BLOCKING FINDINGS`
- `FAIL — BLOCKERS REMAIN`
- `INSUFFICIENT EVIDENCE`

## Recommended Next Gate

- Corrective Review / Production Readiness / Go-No-Go / Other


---

## Document Control

| Field | Value |
|---|---|
| Artifact ID | `{{artifact_id}}` |
| Classification | `Audits` |
| Artifact Type | `Audit Report` |
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
