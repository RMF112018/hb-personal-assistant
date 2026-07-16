# AEOS Core Templates

This directory contains the governing AEOS artifact templates copied from the
approved AEOS source package.

## Governing templates

| Artifact class | Governing template |
|---|---|
| Architectural Decision Record | `ADRs-template.md` |
| Architecture artifact | `Architecture-template.md` |
| Audit report and evidence assessment | `Audits-template.md` |
| Operator decision, risk acceptance, and Go/No-Go record | `Decisions-template.md` |
| Feature specification | `Features-template.md` |
| Implementation plan and planning artifacts | `Plans-template.md` |
| Plan, architecture, corrective, and readiness review | `Reviews-template.md` |
| Governance standard | `Standards-template.md` |

## Selection rules

- Files matching `*-template.md` are the only governing AEOS core templates.
- Do not add shortened aliases or alternate templates for the same artifact
  class.
- Specialized workflow artifacts that are not core AEOS artifact classes belong
  under `.ai/templates/goal-loop/` or another explicitly governed domain folder.
- Evidence indexes, checkpoint requests, authorizations, work-item ledgers, and
  finding ledgers are goal-loop control artifacts, not competing core templates.
- When a template needs revision, amend the governing `*-template.md` file
  through the approved AEOS governance process rather than creating an alias.

## Removed overlapping aliases

The cleanup intentionally removed these non-governing duplicates:

- `architecture_artifact.md`
- `audit_report.md`
- `evidence_package.md`
- `go_no_go_record.md`
- `implementation_plan.md`
- `repository_truth_report.md`
