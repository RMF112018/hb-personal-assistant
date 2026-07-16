---
title: "{{title}}"
artifact_id: "REVIEW-{{id}}"
classification: "Reviews"
artifact_type: "Review Report"
version: "0.1"
status: "Draft"
date_created: "{{date:YYYY-MM-DD}}"
date_updated: "{{date:YYYY-MM-DD}}"
review_type: "{{review_type}}"
reviewer: "{{reviewer}}"
repository: "{{repository}}"
target_branch_pr_commit: "{{target_branch_pr_commit}}"
reviewed_artifact: "{{reviewed_artifact}}"
objective: "{{objective}}"
governing_sources: []
evidence_references: []
related_findings: []
tags:
  - aeos
  - review
---

# {{title}}

**Classification:** Reviews
**Artifact Type:** Review Report
**Version:** 0.1
**Status:** Draft

## Conclusion

State the review outcome first.

## Review Type

Plan Review / Architecture Review / Corrective Review / Readiness Review / Other

## Review Scope

-

## Target

- Repository:
- Branch / PR / Commit:
- Artifact reviewed:
- Objective:

## Governing Sources

-

## Available Evidence

-

## Assumptions and Limitations

-

## Verified Facts

-

## Findings

| ID | Severity | Finding | Evidence | Required Change | Status |
|---|---|---|---|---|---|
| `REV-F-...` |  |  |  |  | Open |

## Objective and Scope Alignment

-

## Architecture Conformance

-

## Missing Work

-

## Unnecessary Work or Scope Expansion

-

## Migration and Rollback Assessment

-

## Security and Trust-Boundary Assessment

-

## Compatibility Assessment

-

## Testing and Evidence Assessment

-

## Observability and Failure-Handling Assessment

-

## Required Changes

| ID | Required Change | Rationale | Verification |
|---|---|---|---|
| `RC-...` |  |  |  |

## Disposition

Select one:

- `APPROVE`
- `APPROVE WITH CHANGES`
- `REVISE`
- `REJECT`

## Recommended Next Gate

-


---

## Document Control

| Field | Value |
|---|---|
| Artifact ID | `{{artifact_id}}` |
| Classification | `Reviews` |
| Artifact Type | `Review Report` |
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
