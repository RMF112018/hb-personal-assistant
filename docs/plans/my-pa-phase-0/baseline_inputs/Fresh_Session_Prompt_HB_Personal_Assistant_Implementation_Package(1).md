# Fresh Session Prompt — Comprehensive Implementation Package for HB Personal Assistant + Work Product Intelligence System

## Operating Context

You are starting a fresh session. Your objective is to generate a complete, developer-ready implementation package for Bobby Fetting’s **HB Personal Assistant + Work Product Intelligence System**.

This project was previously referred to as the “HB Daily Brief + Work Product Intelligence System,” but that name is now superseded. The system is not merely a daily brief tool. The Daily Brief is one module of a broader local-first personal assistant that will provide operational memory, action/work-product intelligence, meeting prep, source-linked retrieval, file review support, and eventually safe interactive assistant workflows.

The target implementation is a Bobby-only local-first MVP. The project will be created in a new repository that does not yet exist.

The final package must align with the structure, rigor, and level of detail of the provided example implementation package, and should be **even more detailed** where the project requires additional auth, privacy, file parsing, evidence, and local automation specificity.

## Mandatory Attached Inputs

Inspect and account for all attached inputs in the session, including:

1. The updated target architecture for **HB Personal Assistant + Work Product Intelligence System**.
2. The HB SharePoint Creator app manifest, if attached.
3. Tenant-resolution proof, if attached or provided in conversation.
4. Certificate-viability proof, if attached.
5. Token cache location/encryption decision, if attached.
6. Auth artifact safety report, if attached.
7. Obsidian vault conventions report, if attached.
8. Prior implementation package ZIP used as a structural/quality benchmark.
9. Any screenshots, notes, logs, commands, or supplemental files Bobby provides.

If any expected attachment is missing or inaccessible, state that explicitly and continue from the available context.

## Core Objective

Generate a complete implementation package for Bobby’s local code agent to implement the HB Personal Assistant + Work Product Intelligence System.

The package must be decision-final wherever possible. Do not leave avoidable open decisions. For decisions delegated to the local agent, define exact decision criteria, validation steps, guardrails, evidence requirements, and default recommendation.

Do not implement the application code in this session. The deliverable is the implementation package for later local code-agent execution.

## Project Name and Scope

Project name:

```text
HB Personal Assistant + Work Product Intelligence System
```

Recommended repo slug:

```text
hb-personal-assistant
```

Daily Brief is a module/workflow, not the project name.

The MVP must include:

- delegated Microsoft Graph auth proof and retrieval workflows;
- Outlook mail retrieval;
- Outlook calendar/calendarView retrieval;
- attachment metadata retrieval;
- OneDrive/SharePoint file metadata retrieval;
- selective file download and bounded parsing;
- source-link registry;
- local SQLite state;
- local model extraction/synthesis using Ollama;
- Obsidian output with generated-section preservation;
- Daily Brief generation as a first assistant workflow;
- launchd morning automation;
- safe diagnostics and evidence.

## Known Closed Decisions

Use the following as closed context unless later evidence directly supersedes it.

| Area | Decision |
|---|---|
| MVP scope | Bobby-only. |
| Target repo | New repo, not yet created. |
| Project name | HB Personal Assistant + Work Product Intelligence System. |
| Old name treatment | “Daily Brief” is a module, not the system name. |
| Recommended repo slug | `hb-personal-assistant`. |
| Future integration | May later integrate with HB Intel. |
| Primary implementation style | Python-first local CLI/agent scripting and file parsing. |
| Microsoft identity app | Existing Entra app registration: HB SharePoint Creator. |
| App/client ID | `08c399eb-a394-4087-b859-659d493f8dc7`. |
| Tenant ID | `0e834bd7-628b-42c8-b9ec-ecebc9719be4`. |
| Tenant display name | `Hedrick Brothers Construction`. |
| Default tenant domain | `hedrickbrothers.com`. |
| Initial tenant domain | `hedrickbrotherscom.onmicrosoft.com`. |
| SharePoint resource root | `https://hedrickbrotherscom.sharepoint.com/`. |
| SharePoint URL correction | SharePoint URL is not the Entra tenant ID. |
| Certificate key ID | `72b2e600-eac6-4b1b-a4b1-4d48048e6667`. |
| Local certificate bundle | `/Users/bobbyfetting/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem`. |
| Certificate viability | Proven: bundle exists, `600` permissions, valid private key, app-only Graph token acquired. |
| App-only token classification | Proven app-only: `roles` present, `scp` absent. |
| Auth default | Delegated Bobby-user auth for runtime mailbox/calendar/file workflows. |
| Delegated Graph proof | Still required in Phase 0. |
| Admin consent | Confirmed by Bobby; runtime effective scope proof still required. |
| File permission posture | `Files.ReadWrite.All` may exist, but runtime behavior must be read-only. |
| Microsoft 365 mutation | Disabled by default for MVP. |
| App registration modification | Permitted only with explicit approval. |
| Token cache location | `~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache.bin`. |
| Optional app-only cache | `~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache-app.bin`. |
| Token cache protection | Strict filesystem permissions for MVP: directories `700`, files `600`. |
| Token cache encryption | Keychain-backed wrapping deferred until launchd/headless reliability is validated. |
| Obsidian vault path | `/Users/bobbyfetting/Documents/Obsidian Vault/`. |
| Obsidian primary output | `Daily Notes/YYYY-MM-DD.md`. |
| Obsidian optional companion output | `AI Outputs/Daily Knowledge Brief - YYYY-MM-DD.md`. |
| Generated section markers | `<!-- HB-DAILY-BRIEF:START -->` / `<!-- HB-DAILY-BRIEF:END -->`. |
| Reference note root | `Work/References/` for MVP. |
| Existing daily note template | Do not mutate automatically. |
| Dataview | Installed/used. |
| Templater | Installed/used. |
| Tasks plugin | Installed/enabled. |
| Task syntax | Plain Markdown-compatible by default; optional Tasks metadata only with high-confidence due/priority values. |
| Default email lookback | 5 days. |
| Body mention requirement | Include emails where Bobby is mentioned in body even if not in To/Cc. |
| Bobby aliases | Include `Bobby`, `Bobby Fetting`, `Robert Fetting`, `bfetting`, `bfetting@outlook.com`, `bfetting@hedrickbrothers.com`. |
| Sent mail | Include for waiting-on-other detection. |
| Sent mail lookback | 7 days default. |
| Calendar | Primary calendar only for MVP. |
| Calendar window | Yesterday, today, next 2 business days. |
| Project number pattern | `NN-NNN-NN`, regex `\b\d{2}-\d{3}-\d{2}\b`, example `25-123-01`. |
| Project year | First two digits map to project year. |
| Morning run time | 5:00 AM local time or first time the machine is awake after 5:00 AM. |
| Automation | macOS launchd. |
| Weekend behavior | Manual-only unless later approved. |
| File-size cap | Increase beyond 25 MB for contracts, CAD/Revit PDF exports, and drawing packages. |
| Recommended large-file controls | Default 100 MB, PDF 250 MB, CAD/Revit export PDF 300 MB, warn above 100 MB, manual approval above 300 MB. |
| OCR | Deferred for MVP. |
| Native CAD/Revit parsing | Out of scope for MVP; exported PDFs only. |
| External LLMs | Disabled by default. Local Ollama preferred. |
| Local state | SQLite canonical store. |
| Vector search | SQLite-compatible vector search preferred after deterministic retrieval works. |
| Source traceability | Mandatory for every generated output. |

## Known Evidence Status

The package must distinguish proven facts from proof still required.

### Already Proven

- Tenant ID and organization were resolved through Azure CLI + Microsoft Graph `/organization`.
- Certificate bundle exists and has restrictive permissions.
- Private key is valid.
- Certificate-backed app-only Graph token acquisition succeeded.
- Token claims classified the certificate-backed token as app-only.
- Token cache location/protection decision is complete.
- Obsidian vault conventions were inspected.
- Tasks plugin is installed/enabled.

### Still Required

The package must require the local agent to obtain **delegated Graph capability proof** before implementing production retrieval workflows.

Required delegated proof targets:

- `/me`;
- Outlook mail metadata;
- one safe Outlook message body retrieval;
- Outlook calendar/calendarView;
- attachment metadata;
- OneDrive/SharePoint file metadata;
- one controlled eligible file download if allowed;
- token claim proof showing delegated `scp`;
- Bobby user context proof;
- no mailbox/calendar workflow using app-only `roles`.

## Required Research Posture

Before generating the final package, perform exhaustive subject-matter research using current primary-source documentation wherever available.

Use and cite current official sources for:

### Microsoft Identity / Entra / MSAL

Research:

- delegated vs application permissions;
- public client vs confidential client behavior;
- localhost redirect / desktop auth patterns;
- certificate-backed confidential client authentication;
- MSAL token caching in Python;
- token claim inspection: `scp` vs `roles`;
- admin consent;
- app-only mailbox/calendar risks;
- Exchange Application RBAC / app access scoping;
- safe Graph proof commands.

### Microsoft Graph Mail

Research:

- message listing;
- `$select`;
- message body/bodyPreview;
- attachments;
- immutable IDs;
- conversation IDs;
- paging, filtering, sorting, throttling;
- sent mail retrieval;
- categories/flags as future write-back only;
- delta query fit for later phases.

### Microsoft Graph Calendar

Research:

- `calendarView` vs `/events`;
- recurring occurrence behavior;
- attendees, organizer, location, body, online meeting;
- private/cancelled events;
- event attachments;
- delta query/change notifications later.

### Microsoft Graph Files / OneDrive / SharePoint

Research:

- `driveItem`;
- resolving OneDrive/SharePoint files;
- sharing/reference links;
- downloading file content;
- Microsoft Search;
- `Files.ReadWrite.All` risk and read-only runtime behavior;
- throttling;
- large file handling.

### Local File Parsing

Research current Python libraries and tradeoffs for:

- PDF text extraction;
- DOCX parsing;
- XLSX parsing;
- PPTX parsing;
- CSV/TXT/Markdown parsing;
- MIME detection;
- file hashing;
- encrypted/password-protected file handling;
- scanned PDF/OCR deferral;
- parser failure isolation;
- large construction PDF handling.

### Obsidian / Markdown / Vault Integration

Research:

- Markdown/frontmatter conventions;
- Obsidian wikilinks and Markdown links;
- Dataview-friendly YAML;
- Tasks plugin-compatible syntax;
- safe generated-section writing;
- user edit preservation;
- vault scanning/indexing;
- limitations of direct vault writes.

### Ollama / Local Model Routing

Research:

- structured JSON outputs;
- embeddings;
- model routing;
- local inference constraints on MacBook Pro M4 with 24 GB memory;
- qwen/llama model availability;
- safe prompt/output logging controls;
- fallback and validation strategies.

### Local Storage / Search / Vector

Research:

- SQLite;
- migrations;
- sqlite-vec or equivalent;
- LanceDB/Chroma/FAISS comparison only if useful;
- idempotent sync;
- source-link registry;
- run ledgers;
- evidence logs;
- backup and retention.

### macOS Automation

Research:

- launchd scheduling;
- catch-up-after-wake behavior or practical approximation;
- environment variables;
- working directory;
- stdout/stderr logging;
- failure visibility;
- manual dry-run and kickstart operations.

## Required Package Structure

Produce a downloadable ZIP package with this minimum structure. You may add more files where beneficial.

```text
HB_Personal_Assistant_Implementation_Package/
  00_README.md
  01_Final_Target_Architecture.md
  02_Final_Implementation_Plan.md
  03_Subject_Matter_Research_Report.md
  04_Auth_And_Permissions_Model.md
  05_Delegated_Graph_Proof_Specification.md
  06_Graph_Integration_Specification.md
  07_Local_Data_Model_And_Source_Link_Registry.md
  08_File_Retrieval_And_Ingestion_Specification.md
  09_Obsidian_Output_And_Vault_Integration_Specification.md
  10_Model_Routing_And_Extraction_Specification.md
  11_CLI_Agent_And_Automation_Specification.md
  12_Risk_Exposure.md
  13_Standards_And_Best_Practices.md
  14_Testing_Validation_And_Evidence_Plan.md
  15_Acceptance_Criteria_And_Closure_Checklist.md
  16_Architecture_Diagrams.md
  17_Decision_Register.md
  18_Operations_Runbook.md
  19_Privacy_And_Security_Controls.md
  20_Manual_Approval_Gates.md

  prompts/
    Prompt_00_Phase_0_Environment_Auth_And_Vault_Discovery.md
    Prompt_01_Repo_Scaffold_And_Local_Config_Foundation.md
    Prompt_02_Auth_Provider_And_Token_Cache.md
    Prompt_03_Delegated_Graph_Capability_Proof.md
    Prompt_04_Graph_Mail_Calendar_Read_Model.md
    Prompt_05_Local_State_Store_And_Source_Link_Registry.md
    Prompt_06_Body_Mention_Detection_And_Email_Classification.md
    Prompt_07_Action_Extraction_And_Schema_Validation.md
    Prompt_08_Obsidian_Writer_And_Daily_Brief_Module.md
    Prompt_09_Attachment_And_Microsoft_365_File_Link_Discovery.md
    Prompt_10_Selective_File_Ingestion_And_Parsing.md
    Prompt_11_Retrieval_Embeddings_And_Workstream_Context.md
    Prompt_12_Launchd_Automation_And_Diagnostics.md
    Prompt_13_Testing_Hardening_And_Final_Closeout.md

  resources/
    config.example.yml
    model-routing.example.yml
    source-rules.example.yml
    logging.example.yml
    sqlite-schema.sql
    action-extraction.schema.json
    email-classification.schema.json
    meeting-prep.schema.json
    file-review.schema.json
    source-link-types.json
    validation-result-register.md
    evidence-log-template.md
    prompt-execution-log-template.md
    launchd.plist.example
```

## Required Package Quality Bar

The implementation package must be suitable for a local code agent to execute without guessing.

It must include:

- precise objectives;
- decision-final architecture;
- implementation rationale;
- phased execution plan;
- expected files/modules/classes/functions;
- schemas and contracts;
- CLI command designs;
- exact validation commands or pseudo-commands;
- proof/evidence requirements;
- failure modes and mitigations;
- acceptance criteria;
- staged local-agent prompts;
- non-goals;
- risk register;
- standards and best practices;
- operations runbook;
- manual approval gates;
- explicit “do not do” constraints;
- safe rollback and recovery guidance.

## Critical Design Constraints

### 1. Do Not Conflate Delegated and App-Only Auth

Certificate-backed app-only auth is proven as viable, but it must not be used for MVP mailbox/calendar runtime processing.

The implementation package must require Phase 0 delegated Graph proof before retrieval workflows.

The package must include token claim classification:

- delegated token: `scp` present;
- app-only token: `roles` present and `scp` absent;
- mailbox/calendar runtime must fail closed on app-only tokens.

### 2. Delegated Graph Proof Is a Required Gate

No production mail/calendar/file retrieval workflow may be implemented as accepted until the local agent proves:

- `/me`;
- mail metadata;
- message body retrieval;
- calendarView;
- attachment metadata;
- file metadata;
- safe eligible file download if allowed.

### 3. File Permission Is Broad; Runtime Behavior Is Conservative

Even if `Files.ReadWrite.All` is available, runtime file behavior must be read-only.

Write-back to OneDrive/SharePoint is disabled unless explicitly approved in a future phase.

### 4. Body Mention Detection Is Required

The package must specify:

- alias configuration;
- staged body retrieval;
- message caps;
- body privacy handling;
- proof that messages mentioning Bobby in body are included even when he is not To/Cc.

### 5. Obsidian Is the Primary Output System

Use discovered vault conventions:

- primary output: `Daily Notes/YYYY-MM-DD.md`;
- optional companion: `AI Outputs/Daily Knowledge Brief - YYYY-MM-DD.md`;
- generated markers: `<!-- HB-DAILY-BRIEF:START -->` / `<!-- HB-DAILY-BRIEF:END -->`;
- reference root: `Work/References/`;
- plain Markdown tasks first;
- optional Tasks plugin metadata only when high-confidence.

### 6. Source Traceability Is Mandatory

Every generated output must link back to one or more source records:

- daily brief bullets;
- action items;
- meeting prep;
- file summaries;
- waiting items;
- project signals;
- retrieval answers.

### 7. Local-First and Privacy-Conservative

Default to:

- local SQLite;
- local file cache;
- local Ollama;
- local Obsidian output;
- no external LLM;
- no cloud-hosted backend;
- redacted logs;
- no token/secret logging;
- no full email body logs;
- no raw file-content logs.

### 8. Large Files Must Be Handled Deliberately

The previous 25 MB limit is too low.

The package must include:

```yaml
files:
  max_file_size_mb_default: 100
  max_file_size_mb_pdf: 250
  max_file_size_mb_office: 100
  max_file_size_mb_cad_export_pdf: 300
  warn_above_mb: 100
  require_manual_approval_above_mb: 300
  parse_timeout_seconds: 180
  extraction_mode: "bounded"
  ocr_enabled: false
```

### 9. Automation Must Run at 5:00 AM or Catch Up After Wake

The launchd design must target 5:00 AM America/New_York and include practical catch-up behavior when the machine wakes after 5:00 AM.

Weekend behavior is manual-only unless later approved.

### 10. Project Number Detection Is Required

The package must include:

```regex
\b\d{2}-\d{3}-\d{2}\b
```

Examples:

- `25-123-01`
- `26-004-02`

Project year rule:

- first two digits map to year;
- use configurable cutoff logic if historical projects require ambiguity handling.

## Required Decision Register Topics

The decision register must address at least:

- project naming;
- Daily Brief module vs system scope;
- auth mode;
- tenant ID;
- certificate use;
- delegated proof requirement;
- token cache location;
- token cache protection/encryption;
- stack choice;
- repo structure;
- CLI namespace;
- SQLite state;
- vector search;
- source-link registry;
- body mention detection;
- email lookback;
- sent mail inclusion;
- calendar window;
- project-number detection;
- file permission posture;
- file-size caps;
- file ingestion eligibility;
- supported file types;
- Obsidian output path;
- Obsidian generated markers;
- Obsidian task syntax;
- reference-note location;
- Microsoft 365 write-back deferral;
- OCR deferral;
- external LLM prohibition;
- launchd schedule;
- catch-up-after-wake behavior;
- diagnostics/evidence retention;
- manual approval gates.

## Required Validation Plan

The package must include a validation plan proving:

- app registration facts were read correctly;
- tenant ID/domain was resolved;
- certificate path exists/readable;
- certificate-backed token acquisition works;
- delegated token acquisition works or failure is documented;
- delegated token contains `scp`;
- app-only token contains `roles`;
- `/me` works;
- mail retrieval works;
- message body retrieval works;
- body mention detection works;
- calendarView retrieval works;
- attachment metadata retrieval works;
- file metadata retrieval works;
- eligible file download works or failure is documented;
- SQLite migrations work;
- idempotent source upsert works;
- source links are created correctly;
- project number detection works;
- action extraction returns valid JSON;
- model output validation works;
- Obsidian writer preserves user edits;
- generated section markers behave correctly;
- Tasks plugin-compatible output remains plain Markdown-valid;
- Daily Brief generation is repeatable;
- dry-run avoids writes;
- Microsoft 365 write-back remains disabled;
- large file controls work;
- launchd job can be installed, run manually, and verified after wake/catch-up logic;
- sensitive artifact scanning passes.

## Required Prompt Rules for Local Code Agent Prompts

Every generated local-agent prompt must include:

- exact objective;
- required context;
- expected files/modules to inspect or create;
- implementation steps;
- validation commands/tests;
- acceptance criteria;
- explicit instruction not to re-read files still within current context or memory unless needed to verify changed content, inspect unloaded lines, or confirm post-patch behavior;
- prohibition against broad unrelated refactors;
- prohibition against Microsoft 365 write-back unless the prompt is specifically for a future approved write-back phase;
- prohibition against logging tokens, private keys, full email bodies, or full file contents;
- explicit dry-run guidance where relevant.

## Expected Fresh Session Workflow

Follow this workflow:

1. Read the updated target architecture and extract closed decisions.
2. Read the app manifest and summarize app-registration facts.
3. Read tenant/certificate/token-cache/vault convention proof files, if attached.
4. Inspect the prior implementation package ZIP to understand expected package quality and structure.
5. Perform exhaustive subject-matter research with citations.
6. Reconcile research findings against the target architecture.
7. Identify conflicts, residual risks, and missing proof gates.
8. Close all decisions that can reasonably be closed.
9. Generate the complete implementation package as a downloadable ZIP.
10. Provide key Markdown files separately if practical.
11. Include a final response summarizing architecture posture, package contents, unresolved proof gates, and manual approval gates.

## Output Requirements

Produce:

1. A downloadable ZIP implementation package.
2. Separate downloadable links for the most important Markdown files if practical:
   - `00_README.md`
   - `01_Final_Target_Architecture.md`
   - `02_Final_Implementation_Plan.md`
   - `04_Auth_And_Permissions_Model.md`
   - `05_Delegated_Graph_Proof_Specification.md`
   - `17_Decision_Register.md`
3. A concise final response.

Do not implement application code. The deliverable is the implementation package for local code-agent execution.
