# HB Personal Assistant + Work Product Intelligence System — Implementation Package

Prepared: 2026-05-25

## Objective

This package gives Bobby's local code agent a complete implementation plan for the `hb-personal-assistant` repository. It does not implement application code.

## Package Contents

| File | Purpose |
| --- | --- |
| 00_README.md | Package orientation and execution order. |
| 01_Final_Target_Architecture.md | Decision-final target architecture. |
| 02_Final_Implementation_Plan.md | Phased local-agent implementation plan. |
| 03_Subject_Matter_Research_Report.md | Research synthesis and source register. |
| 04_Auth_And_Permissions_Model.md | Delegated/app-only auth model, token cache, permissions, and failure gates. |
| 05_Delegated_Graph_Proof_Specification.md | Mandatory proof gate before production retrieval. |
| 06_Graph_Integration_Specification.md | Mail, calendar, attachment, and file read contracts. |
| 07_Local_Data_Model_And_Source_Link_Registry.md | SQLite and source traceability model. |
| 08_File_Retrieval_And_Ingestion_Specification.md | File download, parser, and large-file controls. |
| 09_Obsidian_Output_And_Vault_Integration_Specification.md | Daily Notes, AI Outputs, references, and marker writes. |
| 10_Model_Routing_And_Extraction_Specification.md | Ollama/local model routing and schema validation. |
| 11_CLI_Agent_And_Automation_Specification.md | CLI surface and launchd automation. |
| 12_Risk_Exposure.md | Risk register and mitigations. |
| 13_Standards_And_Best_Practices.md | Implementation standards. |
| 14_Testing_Validation_And_Evidence_Plan.md | Validation matrix and evidence plan. |
| 15_Acceptance_Criteria_And_Closure_Checklist.md | Definition of done. |
| 16_Architecture_Diagrams.md | ASCII system, auth, run, and source-link diagrams. |
| 17_Decision_Register.md | Closed decisions and proof gates. |
| 18_Operations_Runbook.md | Setup, run, troubleshooting, and recovery. |
| 19_Privacy_And_Security_Controls.md | Redaction, secret hygiene, and local data controls. |
| 20_Manual_Approval_Gates.md | Stop points requiring Bobby approval. |

## Inputs Accounted For

- Fresh-session prompt and target architecture.
- HB SharePoint Creator manifest.
- Certificate viability proof.
- Token cache location/encryption decision.
- Auth artifact safety check.
- Obsidian vault convention report.
- Prior implementation package ZIP as a structural benchmark.

## Execution Order

1. Read `00_README.md`, `01_Final_Target_Architecture.md`, `17_Decision_Register.md`, and `20_Manual_Approval_Gates.md`.
2. Execute prompt files in order from `prompts/Prompt_00...` to `prompts/Prompt_13...`.
3. Do not accept production mail/calendar/file workflows before `05_Delegated_Graph_Proof_Specification.md` is satisfied.
4. Use `resources/` schemas and SQL as contracts.


## Global Guardrails

- Bobby-only local-first MVP.
- Python-first CLI/agent implementation.
- Daily Brief is a module, not the project name.
- Delegated Bobby-user Microsoft Graph auth is the runtime default.
- Certificate-backed app-only auth is proof/admin capability only; it is not MVP mail/calendar runtime.
- Microsoft 365 write-back is disabled.
- External LLMs, OCR, native CAD/Revit parsing, tenant-wide crawls, and Obsidian plugin UI are out of MVP.
- Every generated item must carry source traceability.
- Do not log tokens, private keys, full email bodies, calendar bodies, or full file contents.
- Use dry-run before writes.
- Store auth/cache/SQLite/logs outside the repo.
