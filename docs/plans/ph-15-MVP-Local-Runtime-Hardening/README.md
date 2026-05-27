# HB Personal Assistant — Phase 15 MVP Local Runtime Hardening Package

Generated: `2026-05-27T06:21:40.259870+00:00`

## Purpose

This package guides a local code agent through a focused hardening phase for the `RMF112018/hb-personal-assistant` repository after Phase 14 Prompts 0–8 were reportedly completed through commit:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`

Prompt 9 remains deferred pending Microsoft Graph delegated permissions / tenant-admin consent.

The goal is not to expand the architecture. The goal is to convert the current Phase 14 local-runtime implementation into a verifiable MVP candidate by proving actual behavior, closing code/doc mismatches, tightening validation scope, and producing a durable evidence bundle.

## Required Final Classification

```text
MVP_CANDIDATE_LOCAL_RUNTIME_READY
GRAPH_DELEGATED_PROOF_DEFERRED_PENDING_ADMIN_CONSENT
```

## Package Contents

- `PACKAGE_INDEX.md` — recommended execution order.
- `00_Project_Context_And_Objective.md` — current state, constraints, and success posture.
- `01_Target_Architecture_Phase_15.md` — local-runtime MVP architecture target.
- `02_Repo_Truth_Audit_Requirements.md` — required audit commands and inspections.
- `03_Hardening_Implementation_Plan.md` — implementation sequencing and patch boundaries.
- `04_MVP_Local_Runtime_Acceptance_Criteria.md` — acceptance matrix.
- `05_Validation_And_Evidence_Plan.md` — command matrix and evidence outputs.
- `06_Risk_Register_And_Guardrails.md` — safety, privacy, and delivery risks.
- `07_Deferred_Graph_Consent_Closeout_Runbook.md` — Prompt 9 proof plan after IT consent.
- `08_Commit_And_Handoff_Standards.md` — commit, evidence, and closeout standards.
- `09_Source_Truth_Checklists.md` — code/evidence/security checklist.
- `prompts/` — sequenced code-agent prompts.
- `resources/` — checklists, schemas, and evidence templates.
- `runbooks/` — operator and validation runbooks.

## Non-Negotiable Guardrails

- Work in `RMF112018/hb-personal-assistant`, not `hb-intel`.
- Do not use app-only Graph as a runtime replacement for delegated Bobby-user mail/calendar access.
- Do not implement Microsoft 365 writeback.
- Do not persist full email bodies or full file contents.
- Do not commit tokens, cache files, PEMs, secrets, private local data, or raw Microsoft 365 content.
- Do not re-read files that are still in current context or memory; use targeted reads/greps.
- Treat docs as claims and code/tests/evidence as truth.
- If a validation command fails, classify it accurately and either patch it or document why it is outside this phase.
