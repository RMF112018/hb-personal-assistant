# 01 Objective and Scope

## Repo-truth baseline

- Repository: `RMF112018/hb-personal-assistant`
- Audited HEAD from GitHub connector/static repo inspection: `c52cc757b062fe4baf918bd7227dad5e669e3899`
- App version observed: `1.3.0`
- Frontend package version observed: `0.0.0`
- SQLite schema head observed: `V40`
- Latest merged PR observed: PR #3, `Codex/frontend shell layout p00`
- Local dirty state: not verifiable from this package generation context; local agent must run `git status --short` before editing.
- Local launcher/scheduler runtime state: not verifiable from this package generation context; local agent must run the launcher/scheduler commands listed in Prompt 00.

Repository truth is authoritative. This package is an implementation guide only. Reconfirm every touched path and command before editing.


## Objective

Implement Phase 10 — Local Action Intelligence MVP.

Phase 10 converts existing data into reviewable action. The system should answer:

- What needs Bobby's attention?
- Why does it matter?
- What source supports it?
- Who is waiting on whom?
- What is overdue, stale, or blocked?
- What needs prep before today's meetings?
- What should be included in the Daily Brief?
- What context should be prepared for Claude through MCP?

## In scope

- Local model readiness and profile registry.
- Ollama-first provider with pluggable backend abstraction.
- AI job queue and receipts.
- Task/commitment candidate extraction.
- Follow-up monitor.
- Relationship candidate generation.
- Daily Brief action candidates.
- Obsidian vault indexing, tagging, and marker-bounded writing.
- Claude MCP context packet preparation.
- My Dashboard / Review Queue UI surfaces.
- Golden fixtures, metrics, and no-raw/no-writeback proofs.

## Out of scope

- Email sending.
- Calendar creation/edit/accept/decline/delete.
- Procore writeback.
- Graph writeback.
- External LLM requirement.
- Autonomous final contract, financial, payment, claim, entitlement, schedule, legal, or safety determinations.
- Raw full-body persistence.

## Automation levels

- Level 0: candidates only.
- Level 1: user accepts/rejects/edit candidates.
- Level 2: local internal state/dashboard/brief updates only.
- Level 3: drafts and suggestions requiring approval.
- Level 4: external action; excluded from this phase.
