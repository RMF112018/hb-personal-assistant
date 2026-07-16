---
title: "{{title}}"
artifact_id: "DEC-{{id}}"
classification: "Decisions"
artifact_type: "Decision Record"
version: "0.1"
status: "Draft"
date_created: "{{date:YYYY-MM-DD}}"
date_updated: "{{date:YYYY-MM-DD}}"
decision_owner: "{{decision_owner}}"
author: "{{author}}"
decision_type: "{{decision_type}}"
decision_scope: "{{decision_scope}}"
repository: "{{repository}}"
branch_pr_commit: "{{branch_pr_commit}}"
effective_date: "{{effective_date}}"
review_date: "{{review_date}}"
supersedes: []
superseded_by: []
related_artifacts: []
evidence_references: []
tags:
  - aeos
  - decision
---

# {{title}}

**Classification:** Decisions
**Artifact Type:** Decision Record
**Version:** 0.1
**Status:** Draft

## Decision

State the approved, rejected, deferred, ratified, or risk-accepted decision.

## Decision Type

Operator Decision / Ratification / Approval / Risk Acceptance / Go-No-Go / Other

## Scope

-

## Context

-

## Evidence Reviewed

-

## Options Considered

| Option | Benefits | Risks | Disposition |
|---|---|---|---|
|  |  |  |  |

## Rationale

-

## Conditions

-

## Accepted Risks

| Risk ID | Description | Impact | Mitigation | Accepted By | Expiration / Review |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## Required Actions

| Action | Owner | Due / Gate | Evidence Required | Status |
|---|---|---|---|---|
|  |  |  |  | Open |

## Consequences

-

## Effective Date and Duration

- Effective date:
- Review date:
- Expiration:
- Revocation conditions:

## Disposition

`APPROVED / REJECTED / DEFERRED / RATIFIED / GO / CONDITIONAL GO / NO GO / INSUFFICIENT EVIDENCE`

## Approver Statement

Name, role, authority, and explicit approval language.


---

## Document Control

| Field | Value |
|---|---|
| Artifact ID | `{{artifact_id}}` |
| Classification | `Decisions` |
| Artifact Type | `Decision Record` |
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
