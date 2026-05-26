---
title: "HB Personal Assistant — Phase 14 Workstream Intelligence Implementation Package"
repository: "RMF112018/hb-personal-assistant"
project: "HB Personal Assistant + Work Product Intelligence System"
generated_at_utc: "2026-05-26T07:52:59.123696Z"
status: "developer-ready prompt package"
acceptance_posture: "CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER"
---

# 00 — README

## Objective

This package is the comprehensive local-agent prompt package for the next implementation phase of `RMF112018/hb-personal-assistant`.

The project is the **HB Personal Assistant + Work Product Intelligence System**, a Bobby-only local-first personal assistant. Daily Brief generation is one workflow inside the assistant; it is not the full product. This package advances the implementation while Microsoft delegated Graph consent is pending by completing the local workstream intelligence path:

1. repo-truth blocker taxonomy correction;
2. action/work-product intelligence extraction;
3. source-linked action persistence;
4. richer workstream context assembly;
5. marker-bounded Obsidian output with provenance;
6. full local morning-run orchestration;
7. deterministic fixture/evidence harnesses;
8. CI and quality gate hardening;
9. deferred post-consent delegated Graph proof closeout.

## Current Acceptance Posture

The current acceptance classification for the repository should be:

```text
CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER
```

The local agent must not continue describing DNS/network as the active blocker unless fresh command evidence proves DNS failure. The latest user-provided context states that delegated login reached Microsoft and tenant/admin approval remains pending. This package therefore treats DNS evidence in older committed docs as stale historical evidence to be corrected.

## Closed Decisions

The following decisions are closed for this implementation package:

1. The assistant remains Bobby-only for MVP.
2. Runtime state remains local-first and outside the repository.
3. Microsoft 365 access remains delegated, read-only, and user-context based.
4. Certificate-backed app-only auth remains proof/admin only and must not be used for runtime mail/calendar retrieval.
5. No Microsoft 365 writeback is permitted.
6. No full email bodies may be persisted.
7. No full file contents may be persisted.
8. Bounded full-body email inspection may occur in memory only, with redacted excerpts persisted.
9. File ingestion must require provenance-backed source records and must fail closed when provenance is missing.
10. Obsidian writes must be marker-bounded and preserve user content outside markers.
11. Every generated work product must carry source traceability where possible.
12. Work should proceed locally while Graph consent is pending; Graph-dependent proof is deferred, not failed.
13. The next local implementation phase is **Phase 14 — Local Runtime Orchestration & Source-Linked Workstream Intelligence**.
14. Ollama/local model use remains optional and gracefully degraded; deterministic local behavior must pass without Ollama.
15. CI should be introduced with safe, local-only validation that does not require Graph consent.

## Package Contents

| File | Purpose |
|---|---|
| `01_Target_Architecture_And_Closed_Decisions.md` | Phase 14 target architecture, boundaries, and final decisions. |
| `02_Implementation_Plan.md` | Sequenced practical implementation plan. |
| `03_Repo_Truth_Audit_Basis.md` | Repo-truth basis and known current-state findings. |
| `04_Blocker_Taxonomy_And_Admin_Consent_Closeout_Plan.md` | Correct blocker taxonomy and post-consent proof plan. |
| `05_Local_Runtime_Orchestration_Specification.md` | Desired morning-run orchestration behavior and JSON contracts. |
| `06_Action_Work_Product_Intelligence_Specification.md` | Action extraction, waiting-on detection, stable keys, and confidence rules. |
| `07_Source_Link_And_Store_Contract_Specification.md` | Source-link and SQLite persistence rules. |
| `08_Obsidian_Output_And_Provenance_Specification.md` | Daily note/AI output writing, markers, frontmatter, and source provenance. |
| `09_File_Impact_Matrix.md` | Expected touched files and implementation ownership. |
| `10_Risk_Exposure.md` | P0/P1/P2 risk register and mitigations. |
| `11_Standards_And_Best_Practices.md` | Local-first, privacy, CLI, testing, and repo hygiene standards. |
| `12_Testing_Validation_And_Evidence_Plan.md` | Unit/integration/CLI/evidence requirements. |
| `13_Acceptance_Criteria_And_Closure_Checklist.md` | Final acceptance gates. |
| `14_Architecture_Diagrams.md` | Mermaid diagrams for architecture and execution flow. |
| `15_Deferred_Admin_Consent_Proof_Runbook.md` | Exact commands and classification rules after admin approval. |
| `16_CI_And_Quality_Gates.md` | GitHub Actions and local gate plan. |
| `17_Session_Handoff_Template.md` | Required handoff format for continuation. |
| `prompts/` | Sequenced local-agent implementation prompts. |
| `resources/` | JSON contracts, command matrices, templates, and guardrails. |
| `baseline_input_package/` | User-provided audit objective copied for traceability where available. |

## Recommended Execution Order

Run prompts in numerical order from `Prompt_00` through `Prompt_10`. Do not skip `Prompt_00` or `Prompt_01`; the blocker taxonomy correction is a prerequisite for trustworthy evidence.

## Non-Goals

- Do not implement Microsoft 365 writeback.
- Do not implement multi-user or role-based assistant behavior.
- Do not persist full email bodies or full file contents.
- Do not require cloud runtime services.
- Do not require admin consent for local-only deterministic validation.
- Do not make Ollama mandatory for core acceptance.

## Manual Admin-Consent Step

Tenant/admin consent must be completed outside this package before the delegated Graph proof can be fully closed. Until then, Graph-dependent proof should be classified as externally blocked and local-only work should continue.

## Global Operating Rules for the Local Agent

- Work from repo truth only. Do not invent files, APIs, commands, schemas, or behavior.
- Do not re-read files that are still within your current context or memory. Only re-open files when you need to verify changed content, inspect lines not previously loaded, or confirm post-patch behavior.
- Before editing, capture the current repo state:
  - `git remote -v`
  - `git branch --show-current`
  - `git rev-parse HEAD`
  - `git log --oneline -20`
  - `git status --short`
- Keep every change Bobby-only and local-first.
- Do not add Microsoft 365 writeback.
- Do not add multi-user scope.
- Do not persist full email bodies.
- Do not persist full file contents.
- Do not move runtime state into cloud services.
- Do not classify delegated proof as a code failure if the live evidence shows tenant/admin consent is pending.
- Do not classify DNS as the active blocker unless current command evidence proves a live DNS failure.
- Prefer deterministic local fixtures and dry-runs while delegated Graph consent is pending.
- Preserve all existing user work. Do not delete unrelated untracked files or local artifacts.
- Commit after each prompt with the exact expected commit message unless repo truth requires a narrowly adjusted message.
