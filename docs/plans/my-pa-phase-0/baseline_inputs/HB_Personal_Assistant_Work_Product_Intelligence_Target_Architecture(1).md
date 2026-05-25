---
title: "HB Personal Assistant + Work Product Intelligence System — Comprehensive Target Architecture"
owner: "Bobby Fetting"
prepared_for: "Developer Handoff / Local Code Agent Implementation"
version: "2.0"
date: "2026-05-25"
status: "decision-forward target architecture"
project_name: "HB Personal Assistant + Work Product Intelligence System"
project_slug: "hb-personal-assistant"
mvp_scope: "Bobby-only local-first MVP"
primary_output_system: "Obsidian"
obsidian_vault_path: "/Users/bobbyfetting/Documents/Obsidian Vault/"
source_application: "HB SharePoint Creator"
source_application_client_id: "08c399eb-a394-4087-b859-659d493f8dc7"
entra_tenant_id: "0e834bd7-628b-42c8-b9ec-ecebc9719be4"
tenant_display_name: "Hedrick Brothers Construction"
tenant_default_domain: "hedrickbrothers.com"
sharepoint_resource_root: "https://hedrickbrotherscom.sharepoint.com/"
---

# HB Personal Assistant + Work Product Intelligence System — Comprehensive Target Architecture

## 00 — Document Purpose

This document supersedes the prior “HB Daily Brief + Work Product Intelligence System” target architecture.

The project is now named **HB Personal Assistant + Work Product Intelligence System** because the target system is not merely a daily brief generator. The Daily Brief is one important output module, but the broader system is Bobby’s local-first operational assistant for Microsoft 365, local work product, Obsidian, source-linked retrieval, action intelligence, meeting prep, and future safe assistant workflows.

This architecture defines the target state for a Bobby-only local-first MVP that:

- connects to Bobby’s Microsoft 365 context through Microsoft Graph;
- retrieves Outlook email, Outlook calendar, attachments, OneDrive files, SharePoint files, and related Obsidian context;
- selectively ingests and parses work product;
- maintains a durable source-link registry and local operational memory;
- extracts action items, waiting items, commitments, meeting prep, file-review needs, and project/workstream signals;
- writes source-linked outputs into Bobby’s Obsidian vault;
- supports daily brief generation as one workflow within a broader personal assistant architecture;
- defaults to local models, local state, read-only Microsoft 365 behavior, and privacy-conservative diagnostics.

The architecture is designed for a **new repository** that does not yet exist. The first build should be CLI/script-heavy and file-parsing-heavy, with a path to eventual HB Intel integration after the MVP proves value.

---

# 01 — Product Definition

## 1.1 Project Name

**HB Personal Assistant + Work Product Intelligence System**

Short names that may be used in code/docs:

- `HB Personal Assistant`
- `HB Work Assistant`
- `hb-personal-assistant`
- `hb-assistant`

The old phrase “Daily Brief” should be treated as a **module/workflow**, not the system name.

## 1.2 Primary Objective

Develop a local-first personal assistant that can help Bobby answer and act on daily operational questions:

- What do I need to do today?
- Which emails require action?
- Which meetings require preparation?
- Which files need review?
- What am I waiting on from others?
- What did I commit to?
- Which email, meeting, file, note, or prior brief created this action?
- Which project/workstream does this relate to?
- What prior work product supports this issue?
- What do I need to know before a meeting?
- What context should I retrieve before drafting a reply, review, or decision?
- What source-linked memory exists for this topic?

## 1.3 System Outcomes

The assistant must provide:

1. **Daily Brief Generation**
   - Morning operational summary.
   - Priority actions.
   - Meeting prep.
   - Waiting-on-other items.
   - File review queue.
   - Source-linked context.

2. **Operational Memory**
   - Local SQLite state.
   - Source records.
   - Source-link relationships.
   - Action history.
   - Meeting/file/email lineage.
   - Run ledgers and validation evidence.

3. **Action and Work Product Intelligence**
   - Direct asks.
   - Commitments.
   - Follow-ups owed by Bobby.
   - Follow-ups owed to Bobby.
   - File review requests.
   - Meeting prep needs.
   - Decision, contract, risk, financial, safety, and compliance signals.

4. **Source-Linked Retrieval**
   - Deterministic retrieval first.
   - Semantic retrieval only as a supplement.
   - Source IDs and URLs preserved.
   - Obsidian notes linked where relevant.

5. **Safe Interactive Assistant Foundation**
   - CLI/agent workflows first.
   - Dry-run by default for risky workflows.
   - No Microsoft 365 mutation in MVP.
   - Future safe write-back workflows only after explicit approval.

---

# 02 — Closed Decisions and Current Evidence Status

## 2.1 Closed Decisions

| ID | Decision | Status | Rationale / Evidence |
|---|---|---|---|
| D-001 | MVP is Bobby-only. | Closed | Limits scope, permissions, and data exposure. |
| D-002 | Target repo is a new repo. | Closed | Avoids entangling early personal-assistant scripting with HB Intel until MVP is proven. |
| D-003 | System is local-first. | Closed | Protects mailbox, calendar, file, and Obsidian content. |
| D-004 | Microsoft 365 remains the source system. | Closed | Outlook, Exchange, OneDrive, and SharePoint are read as source systems. |
| D-005 | Obsidian is the primary human-facing output system. | Closed | Daily brief and reference outputs should be readable/editable in the vault. |
| D-006 | Local SQLite is the canonical MVP state store. | Closed | Needed for idempotency, lineage, actions, and run history. |
| D-007 | SQLite-compatible vector search is preferred for MVP. | Closed | Avoids a separate vector service during MVP. |
| D-008 | Source-link registry is first-class. | Closed | Every generated item must trace to source records. |
| D-009 | Default email lookback is 5 days. | Closed | User-specified. |
| D-010 | Include emails where Bobby is body-mentioned even if not in To/Cc. | Closed | User-specified. |
| D-011 | Use existing Entra app registration: HB SharePoint Creator. | Closed | User-specified. |
| D-012 | App/client ID is `08c399eb-a394-4087-b859-659d493f8dc7`. | Closed | Manifest/proof context. |
| D-013 | Tenant ID is `0e834bd7-628b-42c8-b9ec-ecebc9719be4`. | Closed | Proven via Azure CLI + Microsoft Graph `/organization`. |
| D-014 | Tenant display name is `Hedrick Brothers Construction`. | Closed | Proven via Graph `/organization`. |
| D-015 | Default domain is `hedrickbrothers.com`. | Closed | Proven via Graph `/organization`. |
| D-016 | Initial tenant domain is `hedrickbrotherscom.onmicrosoft.com`. | Closed | Proven via Graph `/organization`. |
| D-017 | SharePoint resource root is `https://hedrickbrotherscom.sharepoint.com/`. | Closed | User-provided. Not a tenant ID. |
| D-018 | Local certificate bundle path is `/Users/bobbyfetting/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem`. | Closed | User-provided and locally proven. |
| D-019 | Certificate key ID is `72b2e600-eac6-4b1b-a4b1-4d48048e6667`. | Closed | User-provided; app manifest confirms matching credential context. |
| D-020 | Certificate viability is proven. | Closed | Bundle exists, mode `600`, private key valid, app-only Graph token acquired. |
| D-021 | Certificate-backed token is app-only proof, not default mailbox/calendar runtime. | Closed | App-only token has `roles` present and `scp` absent. |
| D-022 | Delegated Bobby-user auth is the default runtime path. | Closed as target; proof pending | Required for Bobby mailbox/calendar user-context workflows. |
| D-023 | Delegated Graph capability proof remains required before production retrieval. | Open proof gate | Must prove `/me`, mail, bodies, calendar, attachment metadata, file metadata. |
| D-024 | Admin consent is confirmed by Bobby. | Closed | User-provided. Runtime proof still required. |
| D-025 | File permission may include `Files.ReadWrite.All`, but runtime behavior is read-only. | Closed | User-specified; architecture restricts write behavior. |
| D-026 | Microsoft 365 mutation is disabled by default. | Closed | No mark read, categories, flags, calendar edits, To Do tasks, file write-back in MVP. |
| D-027 | App registration modification requires explicit approval. | Closed | User-specified governance. |
| D-028 | Token cache location is `~/Library/Application Support/HB Daily Brief/auth/msal-token-cache.bin` for MVP unless renamed at repo creation. | Closed | Phase 0 decision accepted. Project rename may use equivalent `HB Personal Assistant` path if package standardizes it. |
| D-029 | Token cache protection is strict filesystem permissions for MVP. | Closed | Keychain wrapping deferred until launchd/headless reliability is validated. |
| D-030 | Production auth/state/cache should live outside the git repo. | Closed | Security and hygiene. |
| D-031 | Python-first MVP is recommended. | Closed recommendation | Best fit for MSAL, file parsing, SQLite, Ollama, launchd, and local scripts. |
| D-032 | Obsidian vault path is `/Users/bobbyfetting/Documents/Obsidian Vault/`. | Closed | User-provided and inspected. |
| D-033 | Obsidian output should use `Daily Notes/YYYY-MM-DD.md` as the primary daily surface. | Closed | Vault convention discovery. |
| D-034 | Optional companion output may use `AI Outputs/Daily Knowledge Brief - YYYY-MM-DD.md`. | Closed | Vault convention discovery. |
| D-035 | Generated markers: `<!-- HB-DAILY-BRIEF:START -->` / `<!-- HB-DAILY-BRIEF:END -->`. | Closed | Vault convention recommendation. |
| D-036 | Tasks plugin is installed/enabled. | Closed | Vault convention discovery updated. |
| D-037 | Generated tasks must remain plain Markdown compatible first. | Closed | Tasks metadata optional only for high-confidence due/priority values. |
| D-038 | Reference notes should live under `Work/References/` for MVP. | Closed recommendation | Work-operational source context. |
| D-039 | Do not automatically change existing Obsidian Daily Note template. | Closed | Avoids altering user vault behavior. |
| D-040 | Project number pattern is `NN-NNN-NN`, e.g. `25-123-01`. | Closed | User-specified. |
| D-041 | Project year derives from first two digits: `25` → `2025`. | Closed | User-specified and inferred rule. |
| D-042 | Morning automation target is 5:00 AM local time or first machine-awake time after 5:00 AM. | Closed | User-specified. |
| D-043 | File-size cap must be increased beyond 25 MB. | Closed | User-specified due to contract files, CAD/Revit PDF exports, and large drawing packages. |
| D-044 | OCR remains deferred for MVP. | Closed | User-specified unless future proof shows low-risk/high-value option. |
| D-045 | External LLMs are disabled by default; local Ollama preferred. | Closed | Privacy posture. |
| D-046 | CLI/agent workflow precedes Obsidian plugin or UI. | Closed | User’s preferred implementation style. |
| D-047 | Full HB Intel integration is later-phase, not MVP. | Closed | Avoids scope expansion. |

## 2.2 Required Proof Gates Still Pending

The package must require the local agent to obtain and document:

1. Delegated `/me` access under Bobby’s user context.
2. Delegated Outlook mail metadata retrieval.
3. Delegated Outlook message body retrieval for body-mention detection.
4. Delegated Outlook calendar/calendarView retrieval.
5. Delegated attachment metadata retrieval.
6. Delegated OneDrive/SharePoint file metadata retrieval.
7. Controlled eligible file download proof if permissions allow.
8. Token claim proof:
   - delegated token contains `scp`;
   - delegated token identifies Bobby’s user context;
   - token tenant ID is `0e834bd7-628b-42c8-b9ec-ecebc9719be4`;
   - mailbox/calendar workflows do not rely on app-only `roles`.

---

# 03 — Non-Goals for MVP

The MVP must not include:

- tenant-wide mailbox ingestion;
- other users’ mailboxes;
- shared mailbox workflows;
- automatic email sending;
- marking emails read;
- moving/deleting email;
- email category/flag mutation;
- calendar event creation/update/decline;
- Outlook task / Microsoft To Do task creation;
- Microsoft 365 file write-back;
- tenant-wide SharePoint crawl;
- broad OneDrive crawl unrelated to source-linked workflows;
- native CAD/Revit model parsing;
- OCR for scanned documents;
- ZIP extraction beyond safe metadata handling;
- Obsidian plugin UI;
- cloud-hosted backend service;
- external LLM dependency;
- production multi-user identity;
- unbounded document crawling;
- uncontrolled agentic write actions.

---

# 04 — System Context

## 4.1 Source Systems

| Source | Role | MVP Treatment |
|---|---|---|
| Outlook Mail / Exchange Online | Inbound/sent communication, commitments, waiting-on-other detection. | Delegated Graph read. |
| Outlook Calendar | Meetings, prep, follow-up, planning context. | Delegated Graph `calendarView` read. |
| Email attachments | Work-product sources linked to messages. | Discover metadata; selectively download/parse. |
| Calendar attachments | Work-product sources linked to meetings. | Discover metadata where supported; selectively ingest. |
| OneDrive files | Cloud files linked from mail/calendar or retrieved as relevant context. | Resolve, metadata read, selective download. |
| SharePoint files | Project/work product files linked from messages, meetings, and references. | Resolve, metadata read, selective download. |
| Obsidian vault | Human-facing output and local knowledge base. | Read conventions and relevant notes; write marker-bounded generated output. |
| Local file cache | Processing cache for eligible files. | Hash-based, outside repo/vault by default. |
| Local SQLite | Canonical state and source-link registry. | Outside repo in Application Support. |
| Local Ollama | Model runtime for extraction/synthesis/embeddings. | Local-only by default. |
| launchd | macOS automation. | 5:00 AM or first awake after 5:00 AM. |

## 4.2 Core Boundary

```text
MacBook Pro
  ├─ New local repo: hb-personal-assistant
  ├─ Python-first CLI / agent scripts
  ├─ Microsoft Graph delegated auth and retrieval
  ├─ Certificate-backed app-only proof capability
  ├─ Local SQLite state
  ├─ Local file cache
  ├─ Local parser/extraction pipeline
  ├─ Local Ollama model routing
  ├─ Obsidian vault output
  └─ launchd automation
```

---

# 05 — High-Level Architecture

```text
Microsoft 365
  ├─ Outlook Mail
  ├─ Sent Mail
  ├─ Outlook Calendar
  ├─ Email Attachments
  ├─ Calendar Attachments
  ├─ OneDrive Files
  └─ SharePoint Files
        │
        ▼
Auth + Graph Integration Layer
  ├─ Delegated Auth Provider
  ├─ Certificate Proof Provider
  ├─ Token Cache Manager
  ├─ Mail Client
  ├─ Calendar Client
  ├─ Attachment Client
  ├─ Drive/File Client
  ├─ Search/Link Resolver
  ├─ Retry/Throttle Policy
  └─ Graph Error Normalizer
        │
        ▼
Source Normalization Layer
  ├─ Email Normalizer
  ├─ Recipient/Identity Normalizer
  ├─ Calendar Event Normalizer
  ├─ Attachment Normalizer
  ├─ DriveItem Normalizer
  ├─ File Metadata Normalizer
  └─ Obsidian Note Normalizer
        │
        ▼
Local Operational Memory
  ├─ SQLite source_records
  ├─ emails / calendar_events / files
  ├─ source_links
  ├─ action_items
  ├─ assistant_runs
  ├─ sync_state
  ├─ parser_outputs
  ├─ evidence logs
  └─ vector index
        │
        ▼
Work Product Intelligence Layer
  ├─ Deterministic rules
  ├─ Project-number detection
  ├─ Body-mention detection
  ├─ Action extraction
  ├─ Meeting-prep extraction
  ├─ Waiting-on-other detection
  ├─ File-review detection
  ├─ Risk/contract/safety signal detection
  ├─ Schema validation
  └─ Confidence scoring
        │
        ▼
Assistant Output Layer
  ├─ Daily Brief section in Daily Notes
  ├─ Optional AI Outputs companion note
  ├─ Work/References source notes
  ├─ Action register notes
  ├─ Meeting prep notes
  ├─ File review notes
  └─ Retrieval answers / future assistant workflows
        │
        ▼
User Interaction Layer
  ├─ CLI
  ├─ Local code agent workflows
  ├─ Obsidian review/edit loop
  ├─ launchd morning automation
  └─ Future HB Intel / UI integration
```

---

# 06 — Recommended Repository and Runtime Architecture

## 6.1 Recommended Project Slug

```text
hb-personal-assistant
```

## 6.2 Recommended Stack

Python-first MVP.

Rationale:

- MSAL Python supports delegated and confidential-client flows.
- Python has mature file parsing libraries for PDF/DOCX/XLSX/PPTX/CSV/Markdown.
- SQLite is built in.
- Ollama integration is straightforward over local HTTP.
- launchd workflows can run Python CLI commands reliably.
- The MVP is scripting/file-parsing heavy.
- Later HB Intel integration can consume exports or packages once workflows are proven.

TypeScript may be introduced later only if the project moves toward a UI, SPFx, or HB Intel module.

## 6.3 Proposed Repository Layout

```text
hb-personal-assistant/
  README.md
  pyproject.toml
  .env.example
  .gitignore

  config/
    config.example.yml
    model-routing.example.yml
    source-rules.example.yml
    logging.example.yml

  docs/
    architecture/
      target-architecture.md
      architecture-diagrams.md
    decisions/
      decision-register.md
      token-cache-location-and-encryption.md
    evidence/
      phase-0-tenant-resolution.md
      phase-0-certificate-viability-proof.md
      phase-0-delegated-graph-proof.md
      phase-0-auth-artifact-safety-check.md
      vault-conventions.md
    validation/
      acceptance-criteria.md
      evidence-log-template.md

  src/
    hb_assistant/
      __init__.py
      cli/
      auth/
      graph/
      normalize/
      store/
      links/
      files/
      obsidian/
      models/
      extraction/
      retrieval/
      assistant/
      automation/
      diagnostics/
      validation/

  scripts/
    proofs/
      prove_certificate_auth.py
      prove_delegated_graph_access.py
    maintenance/

  tests/
    unit/
    integration/
    fixtures/

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
    Prompt_10_Select_File_Ingestion_And_Parsing.md
    Prompt_11_Retrieval_Embeddings_And_Workstream_Context.md
    Prompt_12_Launchd_Automation_And_Diagnostics.md
    Prompt_13_Testing_Hardening_And_Final_Closeout.md

  resources/
    sqlite-schema.sql
    action-extraction.schema.json
    email-classification.schema.json
    meeting-prep.schema.json
    file-review.schema.json
    source-link-types.json
```

## 6.4 Production Local State Layout

Use macOS Application Support.

```text
~/Library/Application Support/HB Personal Assistant/
  auth/
    msal-token-cache.bin
    msal-token-cache-app.bin
  config/
    config.yml
    model-routing.yml
    source-rules.yml
  db/
    hb-personal-assistant.sqlite
  cache/
    files/
    extracted-text/
    summaries/
  embeddings/
    sqlite-vec/
  logs/
    run-logs/
    error-logs/
  evidence/
    auth-proof/
    graph-proof/
    validation/
```

If the implementation package chooses to preserve the already-proven path `~/Library/Application Support/HB Daily Brief/`, it must document a migration path to `HB Personal Assistant`. Recommended final path is the renamed project path above.

## 6.5 CLI Namespace

Recommended CLI:

```bash
hb-assistant
```

Required commands:

```bash
hb-assistant auth login
hb-assistant auth status
hb-assistant auth logout
hb-assistant auth clear-cache
hb-assistant diagnostics env
hb-assistant diagnostics auth
hb-assistant diagnostics graph
hb-assistant vault inspect
hb-assistant sync mail --lookback 5d
hb-assistant sync calendar --window default
hb-assistant links discover
hb-assistant files ingest --eligible-only
hb-assistant actions extract
hb-assistant brief generate --date today
hb-assistant brief generate --dry-run
hb-assistant actions list --status open
hb-assistant search "GMP Exhibit"
hb-assistant run morning
```

---

# 07 — Identity, Authentication, and Permission Architecture

## 7.1 Known App Registration Inputs

| Item | Value |
|---|---|
| App registration name | HB SharePoint Creator |
| Client/application ID | `08c399eb-a394-4087-b859-659d493f8dc7` |
| Tenant ID | `0e834bd7-628b-42c8-b9ec-ecebc9719be4` |
| Tenant display name | `Hedrick Brothers Construction` |
| Default domain | `hedrickbrothers.com` |
| Initial tenant domain | `hedrickbrotherscom.onmicrosoft.com` |
| Certificate key ID | `72b2e600-eac6-4b1b-a4b1-4d48048e6667` |
| Certificate bundle | `/Users/bobbyfetting/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem` |
| SharePoint root | `https://hedrickbrotherscom.sharepoint.com/` |
| Admin consent | Confirmed by Bobby |
| App modification | Requires explicit approval |

## 7.2 Auth Mode Rules

### Default Runtime Auth

Use **delegated Bobby-user auth** for:

- `/me`;
- mail metadata;
- message bodies;
- calendar/calendarView;
- attachment metadata;
- OneDrive/SharePoint file metadata;
- eligible file download.

### Certificate-Backed Auth

Use certificate-backed auth for:

- proof of confidential-client capability;
- app-only workflows only where explicitly approved;
- future provisioning/admin tasks if separately scoped.

The certificate proof is complete, but it does **not** authorize app-only mailbox/calendar processing.

### Token Claim Classification

The auth module must classify token type:

| Token Shape | Classification |
|---|---|
| `scp` present, `roles` absent or irrelevant | Delegated |
| `roles` present, `scp` absent | App-only |
| neither present | Invalid/ambiguous |
| both present | Must fail closed until explained |

Mailbox/calendar workflows must fail closed if given app-only tokens during MVP.

## 7.3 Required Delegated Graph Proof

Before implementing production retrieval, the local agent must produce:

```text
docs/evidence/phase-0-delegated-graph-proof.md
```

It must prove:

- delegated token acquisition succeeds;
- token includes `scp`;
- token tenant ID is `0e834bd7-628b-42c8-b9ec-ecebc9719be4`;
- Bobby user context resolves correctly;
- `/me` succeeds;
- mail metadata retrieval succeeds;
- one safe message body retrieval succeeds;
- calendarView retrieval succeeds;
- attachment metadata retrieval succeeds where available;
- file metadata retrieval succeeds;
- controlled eligible file download succeeds if permissions allow;
- failures are documented with endpoint, HTTP status, required scope, and remediation.

## 7.4 Token Cache

Final MVP decision:

```yaml
auth:
  token_cache:
    location: "~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache.bin"
    app_only_cache_location: "~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache-app.bin"
    protection: "strict-filesystem-permissions"
    directory_permissions: "700"
    file_permissions: "600"
    keychain_wrapping: "deferred"
    keychain_revisit_trigger: "after launchd/headless reliability validation"
```

CLI must support:

```bash
hb-assistant auth clear-cache
hb-assistant auth logout
hb-assistant diagnostics auth
```

---

# 08 — Microsoft Graph Integration Architecture

## 8.1 Graph Client Boundaries

```text
src/hb_assistant/graph/
  mail_client.py
  calendar_client.py
  attachment_client.py
  drive_client.py
  search_client.py
  link_resolver.py
  graph_error.py
  throttle.py
  query_builders.py
  dto_mappers.py
```

Graph clients return normalized DTOs only. They must not write Markdown, call models, or decide presentation.

## 8.2 Mail Retrieval

### Default Window

```yaml
email:
  default_lookback_days: 5
```

### Candidate Inclusion

Include:

- Inbox messages received in last 5 days;
- messages where Bobby is in `To`;
- messages where Bobby is in `Cc`;
- messages where Bobby is mentioned in body;
- flagged messages within configured cap;
- high-importance messages;
- messages from priority senders/domains;
- messages with project-number pattern `\b\d{2}-\d{3}-\d{2}\b`;
- messages with configured workstream keywords;
- messages related to upcoming meetings;
- messages with relevant attachments;
- sent messages for waiting-on-other detection.

### Bobby Mention Aliases

Default config:

```yaml
bobby_mentions:
  - "Bobby"
  - "Bobby Fetting"
  - "Robert Fetting"
  - "bfetting"
  - "bfetting@outlook.com"
  - "bfetting@hedrickbrothers.com"
```

The delegated proof step should refine aliases based on `/me` and mailbox identities.

### Sent Mail

```yaml
sent_mail:
  enabled: true
  lookback_days: 7
  purpose: "waiting_on_others_detection"
```

Sent mail must not dominate the brief. It is used to detect unanswered asks and commitments owed by others.

## 8.3 Calendar Retrieval

Use primary calendar `calendarView`.

Default:

```yaml
calendar:
  calendars: "primary_only"
  include_yesterday: true
  include_today: true
  lookahead_business_days: 2
  include_private_events: "blocked_time_only"
  include_cancelled_events: false
```

The system must handle recurring occurrences, organizer, attendees, location, online meeting URLs, body/description, attachments/links, and prep classification.

## 8.4 Attachments

Must distinguish:

- `fileAttachment`;
- `itemAttachment`;
- `referenceAttachment`.

All attachment records become source records. Only eligible attachments are downloaded and parsed.

## 8.5 OneDrive / SharePoint Files

The drive client must support:

- URL extraction from messages/events;
- sharing link resolution;
- file metadata retrieval;
- file content download for eligible files only;
- web URL preservation;
- drive ID / drive item ID / site ID preservation;
- duplicate detection by content hash;
- source links back to emails/events/actions/briefs.

Runtime behavior remains read-only.

---

# 09 — Project and Workstream Recognition

## 9.1 Project Number Pattern

Canonical pattern:

```regex
\b\d{2}-\d{3}-\d{2}\b
```

Examples:

```text
25-123-01
26-004-02
24-999-01
```

## 9.2 Project Year Rule

The first two digits map to project year:

```text
25-123-01 → 2025
26-123-01 → 2026
99-123-01 → 1999 or configurable cutoff logic if old project support is needed
```

Recommended MVP year logic:

```text
00–79 → 2000–2079
80–99 → 1980–1999
```

The cutoff should be configurable.

## 9.3 Project Signal Sources

Project/workstream association may come from:

- email subject;
- email body;
- attachment filename;
- attachment text;
- calendar subject/body;
- file names;
- SharePoint/OneDrive paths;
- Obsidian note links/tags;
- user-configured source rules.

Project number exact matches outrank semantic similarity.

---

# 10 — Local Data Architecture

## 10.1 Storage Requirements

SQLite must support:

- idempotent sync;
- source record lineage;
- source links;
- action status;
- file ingestion status;
- brief/run history;
- token-independent evidence logs;
- Obsidian write tracking;
- user edit preservation;
- project/workstream recognition;
- parser/model version tracking.

## 10.2 Core Tables

The implementation package should include an expanded `sqlite-schema.sql` with, at minimum:

- `source_records`
- `emails`
- `calendar_events`
- `files`
- `source_links`
- `action_items`
- `assistant_runs`
- `sync_state`
- `parser_outputs`
- `model_outputs`
- `obsidian_writes`
- `project_signals`
- `validation_results`

## 10.3 `project_signals`

```sql
CREATE TABLE project_signals (
  id TEXT PRIMARY KEY,
  source_record_id TEXT NOT NULL,
  project_number TEXT NOT NULL,
  project_year INTEGER,
  signal_location TEXT NOT NULL,
  confidence REAL NOT NULL,
  created_at TEXT NOT NULL,
  evidence_json TEXT,
  FOREIGN KEY (source_record_id) REFERENCES source_records(id)
);
```

## 10.4 `assistant_runs`

Rename the old `brief_runs` concept to `assistant_runs`.

```sql
CREATE TABLE assistant_runs (
  id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  run_date TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  email_count INTEGER DEFAULT 0,
  event_count INTEGER DEFAULT 0,
  file_count INTEGER DEFAULT 0,
  action_count INTEGER DEFAULT 0,
  output_paths_json TEXT,
  model_manifest_json TEXT,
  error_json TEXT
);
```

---

# 11 — Source-Link Registry Architecture

## 11.1 Purpose

The source-link registry is the system’s trust layer. It must answer:

- Which email created this action?
- Which meeting discussed this file?
- Which file was attached or linked?
- Which daily brief included this commitment?
- Which project/workstream does this relate to?
- Which prior Obsidian note provides context?
- Was the relationship direct, inferred, or semantic-only?

## 11.2 Source Types

```text
email
sent_email
calendar_event
email_attachment
calendar_attachment
sharepoint_file
onedrive_file
obsidian_note
daily_brief
assistant_output
action_item
extracted_text
file_summary
meeting_prep_item
project_signal
```

## 11.3 Relationship Types

```text
attached_to
linked_from
mentioned_in
discussed_in
supports_action
requires_review_for
follow_up_for
meeting_prep_for
project_context_for
summarized_by
briefed_in
derived_from
waiting_on
same_conversation_as
same_workstream_as
same_project_as
semantic_match_to
```

## 11.4 Confidence Rules

| Evidence | Confidence |
|---|---:|
| Direct attachment | 1.00 |
| Direct URL in body | 0.95 |
| Exact project number match | 0.90 |
| Same Outlook conversation ID | 0.85 |
| Same calendar invite/thread | 0.80 |
| Same SharePoint path project folder | 0.80 |
| Configured workstream keyword | 0.60 |
| Semantic similarity only | 0.30–0.50 |

Semantic similarity must never outrank direct evidence.

---

# 12 — File Retrieval and Ingestion Architecture

## 12.1 Supported MVP File Types

| Type | MVP Treatment |
|---|---|
| `.pdf` | Digitally readable text extraction; OCR deferred. |
| `.docx` | Text extraction. |
| `.xlsx` | Bounded workbook/sheet extraction. |
| `.pptx` | Slide text extraction. |
| `.csv` | CSV parsing. |
| `.txt` | Plain text ingestion. |
| `.md` | Markdown ingestion. |

## 12.2 Large File Controls

The previous 25 MB cap is too low for construction contracts, CAD/Revit PDF exports, and drawing packages.

Recommended MVP controls:

```yaml
files:
  default_behavior: "read_only"
  selective_ingestion_only: true
  cache_binaries: true
  max_file_size_mb_default: 100
  max_file_size_mb_pdf: 250
  max_file_size_mb_office: 100
  max_file_size_mb_cad_export_pdf: 300
  warn_above_mb: 100
  require_manual_approval_above_mb: 300
  parse_timeout_seconds: 180
  extraction_mode: "bounded"
  ocr_enabled: false
  writeback_enabled: false
```

## 12.3 Large Construction PDF Strategy

For large PDFs:

- Always capture metadata and source links even if parsing is skipped.
- Detect page count.
- Detect whether text is digitally extractable.
- Extract text only within configured size/page/time bounds.
- Allow page sampling for oversized files.
- Do not OCR in MVP.
- Do not parse native CAD/Revit files in MVP.
- Treat CAD/Revit exports as PDFs only.

## 12.4 File Processing Pipeline

```text
Discover metadata
  ↓
Create source record
  ↓
Create source links
  ↓
Score eligibility
  ↓
If eligible and within controls:
    download to local cache
  ↓
Compute hash
  ↓
Detect duplicate
  ↓
Extract bounded text
  ↓
Chunk and summarize
  ↓
Embed if enabled
  ↓
Create optional reference note
  ↓
Link to actions/meetings/briefs
```

---

# 13 — Obsidian Architecture

## 13.1 Vault Root

```text
/Users/bobbyfetting/Documents/Obsidian Vault/
```

## 13.2 Observed Vault Conventions

Observed top-level domains:

- `Work/`
- `Side Hustle/`
- `Knowledge/`
- `Daily Notes/`
- `Templates/`
- `AI Outputs/`
- `Agent Briefs/`

Observed conventions:

- Frontmatter fields: `type`, `domain`, `status`, `tags`, nested `source`, `related`, `owner`, `created`, `updated`, `last_reviewed`.
- Internal links: Obsidian wikilinks.
- External/source links: Markdown links.
- Tags: lowercase hyphenated taxonomy.
- Dataview installed.
- Templater installed.
- Tasks plugin installed/enabled.
- No established vault-wide generated marker convention existed before this project.

## 13.3 Daily Brief Output Convention

Primary:

```text
Daily Notes/YYYY-MM-DD.md
```

Optional companion:

```text
AI Outputs/Daily Knowledge Brief - YYYY-MM-DD.md
```

Generated marker format:

```markdown
<!-- HB-DAILY-BRIEF:START -->
...
<!-- HB-DAILY-BRIEF:END -->
```

Rules:

- Overwrite only inside marker pair.
- Preserve all content outside markers.
- If markers are missing, append a generated block or insert at configured heading.
- If markers are malformed, fail safely and write a recovery/staging note.
- Preserve completed checkbox state when source item identity matches.

## 13.4 Task Syntax

Default generated task format:

```markdown
- [ ] Review updated subcontract exhibit — due 2026-05-25  
  Source: [Email: Updated Exhibit](https://outlook.office.com/...)
```

Optional Tasks-plugin metadata may be used only when source confidence is high and the line remains valid plain Markdown.

Example optional syntax after validation:

```markdown
- [ ] Review updated subcontract exhibit 📅 2026-05-25 🔼
```

The implementation must not assume advanced Tasks plugin syntax until tested against the vault.

## 13.5 Reference Note Convention

Use `Work/References/` for MVP.

Create reference notes only for:

- reusable multi-day context;
- complex email threads;
- high-value file reviews;
- recurring meetings;
- decisions/actions with future retrieval value.

Do not create reference notes for every source object.

---

# 14 — Model and Reasoning Architecture

## 14.1 Local Model Requirement

Use local Ollama models by default. External LLMs are disabled unless explicitly approved later.

## 14.2 Model Roles

| Role | Purpose |
|---|---|
| Triage | Fast noise reduction and relevance scoring. |
| Extraction | Actions, commitments, deadlines, prep, file review. |
| Synthesis | Daily brief and assistant outputs. |
| Validator/fallback | Schema repair/challenge. |
| Embeddings | Semantic retrieval across local records. |
| Deep synthesis | Optional weekly/overnight synthesis. |

## 14.3 Model Rules

- Output must be schema-validated JSON for extraction.
- Output must include source record IDs.
- Output must include confidence.
- Inferred dates must be flagged.
- Models cannot mutate Microsoft 365.
- Models cannot write outside the Obsidian writer.
- Models cannot invent source links.

---

# 15 — Retrieval Architecture

## 15.1 Retrieval Priority

1. Direct source record ID.
2. Outlook conversation ID / message ID.
3. Calendar event ID / iCal UID.
4. File hash / driveItem ID.
5. Exact project number match.
6. Exact sender/domain.
7. Exact date/title.
8. Open action status.
9. Workstream tag/rule.
10. Semantic similarity.

## 15.2 Context Pack

Each assistant run may build a context pack containing:

- today’s meetings;
- yesterday’s follow-ups;
- upcoming meeting prep;
- new candidate emails;
- body-mentioned emails;
- open prior actions;
- waiting-on-other items;
- file review queue;
- related Obsidian notes;
- project signals;
- high-confidence links;
- bounded semantic matches.

---

# 16 — Assistant Workflows

## 16.1 Morning Run

Target:

```yaml
automation:
  morning_run:
    time: "05:00"
    timezone: "America/New_York"
    catch_up_if_machine_wakes_after: true
    weekend_behavior: "manual_only"
```

Pipeline:

```text
launchd triggers run or catch-up after wake
  ↓
load config
  ↓
validate delegated auth
  ↓
sync mail candidates
  ↓
retrieve bodies for mention detection
  ↓
sync calendarView
  ↓
discover links/attachments
  ↓
resolve file metadata
  ↓
score relevance
  ↓
selectively ingest files
  ↓
extract actions/prep/waiting/file review
  ↓
retrieve prior local/Obsidian context
  ↓
generate Daily Brief section
  ↓
write Obsidian output safely
  ↓
persist assistant run ledger
  ↓
write sanitized diagnostics
```

## 16.2 Other Run Types

| Run Type | Purpose |
|---|---|
| `morning` | Standard 5:00 AM/catch-up assistant run. |
| `midday-refresh` | Manual refresh. |
| `end-of-day` | Optional closeout/review. |
| `meeting-prep` | Build context for a specific meeting. |
| `file-review` | Summarize and prepare a source-linked file review. |
| `search` | Source-linked retrieval. |
| `weekly-synthesis` | Optional deep weekly synthesis. |
| `backfill` | Controlled historical processing. |
| `diagnostics` | Health check only. |

---

# 17 — Configuration Architecture

## 17.1 Example Config

```yaml
project:
  name: "HB Personal Assistant + Work Product Intelligence System"
  slug: "hb-personal-assistant"

microsoft:
  app_name: "HB SharePoint Creator"
  client_id: "08c399eb-a394-4087-b859-659d493f8dc7"
  tenant_id: "0e834bd7-628b-42c8-b9ec-ecebc9719be4"
  tenant_display_name: "Hedrick Brothers Construction"
  tenant_domain_default: "hedrickbrothers.com"
  tenant_domain_initial: "hedrickbrotherscom.onmicrosoft.com"
  sharepoint_resource_root: "https://hedrickbrotherscom.sharepoint.com/"
  auth_default: "delegated"
  certificate:
    enabled_for_validation: true
    key_id: "72b2e600-eac6-4b1b-a4b1-4d48048e6667"
    bundle_path: "/Users/bobbyfetting/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem"

auth:
  token_cache:
    delegated_cache_path: "~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache.bin"
    app_only_cache_path: "~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache-app.bin"
    protection: "strict-filesystem-permissions"
    keychain_wrapping: false

email:
  default_lookback_days: 5
  include_body_mentions: true
  include_sent_for_waiting_detection: true
  sent_lookback_days: 7
  include_flagged: true
  include_high_importance: true
  include_junk: false
  include_deleted: false
  include_archive: false
  bobby_mentions:
    - "Bobby"
    - "Bobby Fetting"
    - "Robert Fetting"
    - "bfetting"
    - "bfetting@outlook.com"
    - "bfetting@hedrickbrothers.com"

calendar:
  calendars: "primary_only"
  include_yesterday: true
  lookahead_business_days: 2
  include_private_events: "blocked_time_only"
  include_cancelled_events: false

projects:
  project_number_regex: "\\b\\d{2}-\\d{3}-\\d{2}\\b"
  project_year_cutoff:
    low_century_start: 0
    low_century_end: 79
    high_century_start: 80
    high_century_end: 99

files:
  graph_permission: "Files.ReadWrite.All"
  default_behavior: "read_only"
  writeback_enabled: false
  selective_ingestion_only: true
  max_file_size_mb_default: 100
  max_file_size_mb_pdf: 250
  max_file_size_mb_office: 100
  max_file_size_mb_cad_export_pdf: 300
  warn_above_mb: 100
  require_manual_approval_above_mb: 300
  parse_timeout_seconds: 180
  extraction_mode: "bounded"
  ocr_enabled: false

obsidian:
  vault_path: "/Users/bobbyfetting/Documents/Obsidian Vault/"
  primary_daily_note_path_pattern: "Daily Notes/{YYYY-MM-DD}.md"
  optional_companion_path_pattern: "AI Outputs/Daily Knowledge Brief - {YYYY-MM-DD}.md"
  reference_root: "Work/References"
  generated_marker_start: "<!-- HB-DAILY-BRIEF:START -->"
  generated_marker_end: "<!-- HB-DAILY-BRIEF:END -->"
  preserve_user_edits: true
  tasks_plugin_enabled: true
  task_syntax_default: "plain_markdown"

automation:
  platform: "macOS launchd"
  morning_time: "05:00"
  timezone: "America/New_York"
  catch_up_after_wake: true
  weekend_behavior: "manual_only"

privacy:
  store_full_email_body: false
  store_body_hash: true
  store_extracted_summary: true
  cache_downloaded_files: true
  allow_external_llm: false
  allow_microsoft365_writeback: false
  redact_logs: true
```

---

# 18 — Phased Implementation Plan

## Phase 0 — Environment, Auth, and Vault Proof

Required outputs:

- tenant resolution proof;
- certificate viability proof;
- delegated Graph proof;
- token cache proof;
- auth artifact safety check;
- Obsidian convention report;
- stack/repo recommendation.

Phase 0 must be completed before production retrieval workflows.

## Phase 1 — Repo Scaffold and Configuration

Create repo structure, config model, `.env.example`, `.gitignore`, path manager, logging/redaction utilities, and diagnostics shell.

## Phase 2 — Auth Provider and Token Cache

Implement delegated auth provider, certificate proof provider, token classification, token cache manager, clear-cache/logout behavior, and auth diagnostics.

## Phase 3 — Graph Read Model

Implement mail, calendar, attachment, and file metadata clients. Include delegated proof gates and endpoint-level error reporting.

## Phase 4 — Local State and Source-Link Registry

Implement SQLite schema, migrations, source records, source links, assistant runs, and idempotent upsert.

## Phase 5 — Mail/Calendar Classification and Body Mention Detection

Implement staged retrieval, body mention detection, project-number detection, basic classification, sent-mail waiting-on-other scan.

## Phase 6 — Action Extraction and Schema Validation

Implement deterministic extraction helpers, Ollama model call wrappers, schema validation, confidence scoring, and safe persistence.

## Phase 7 — Obsidian Writer and Daily Brief Module

Implement marker-bounded writer, primary daily note output, optional companion note, task state preservation, source links, and dry-run.

## Phase 8 — File Discovery and Selective Ingestion

Implement attachment/link discovery, DriveItem metadata, selective download, hash cache, parser pipeline, large-file controls, parser failure isolation.

## Phase 9 — Retrieval and Workstream Intelligence

Implement deterministic retrieval, project/workstream linking, optional sqlite-compatible vector search, context pack builder.

## Phase 10 — launchd Automation and Hardening

Implement 5:00 AM/catch-up schedule, logs, manual dry-run, health checks, validation suite, and final acceptance evidence.

---

# 19 — Validation and Evidence Requirements

Required evidence files:

```text
docs/evidence/
  phase-0-tenant-resolution.md
  phase-0-certificate-viability-proof.md
  phase-0-delegated-graph-proof.md
  phase-0-auth-artifact-safety-check.md
  phase-0-vault-conventions.md
  graph-mail-proof.md
  graph-calendar-proof.md
  graph-files-proof.md
  body-mention-detection-proof.md
  project-number-detection-proof.md
  source-link-registry-proof.md
  obsidian-write-proof.md
  daily-brief-sample.md
  tasks-plugin-compatibility-proof.md
  large-file-ingestion-proof.md
  idempotency-proof.md
  dry-run-proof.md
  launchd-proof.md
```

MVP-ready when:

- delegated auth works;
- `/me`, mail, bodies, calendar, file metadata work;
- body-mentioned emails are included;
- project numbers are detected;
- source links are created;
- actions are schema-valid;
- daily brief writes into Obsidian safely;
- user edits are preserved;
- no Microsoft 365 mutation occurs;
- large files are controlled;
- dry-run works;
- 5:00 AM/catch-up automation works;
- safe diagnostics exist.

---

# 20 — Risk Exposure

| Risk | Exposure | Mitigation |
|---|---|---|
| Delegated access fails | MVP retrieval blocked. | Phase 0 proof gate; document scopes/remediation. |
| App-only auth misuse | Mailbox/calendar overexposure. | Fail closed for mailbox/calendar app-only tokens. |
| Broad file permissions | `Files.ReadWrite.All` may allow writes. | Runtime write-back disabled; tests prove no mutation. |
| Large file overload | Contract/drawing PDFs may be huge. | Bounded parsing, size caps, timeouts, manual approval over 300 MB. |
| Missing body mentions | Required inclusion could fail if bodies not retrieved. | Explicit body retrieval strategy and proof. |
| Hallucinated actions | LLM may invent commitments. | Source IDs, schema validation, confidence, inferred flags. |
| Obsidian overwrite | User notes could be damaged. | Marker-bounded writes, staging fallback. |
| Token leakage | Local cache or logs could expose secrets. | Application Support cache, 700/600 perms, redacted logs. |
| launchd silent failure | Morning run may not happen. | Logs, diagnostics, catch-up behavior, manual run command. |
| Tasks plugin syntax mismatch | Generated tasks may behave incorrectly. | Plain Markdown default; optional metadata after validation. |

---

# 21 — Standards and Best Practices

The build must follow:

- delegated-first mailbox/calendar access;
- local-first processing;
- least operational privilege;
- read-only Microsoft 365 behavior by default;
- source traceability for every generated item;
- deterministic rules before semantic/model inference;
- schema-validated model outputs;
- idempotent sync and generation;
- token/secret redaction;
- dry-run support;
- marker-bounded Obsidian writes;
- parser failure isolation;
- no broad unrelated refactors;
- no Microsoft 365 mutation without explicit future approval;
- no external LLM without explicit future approval.

---

# 22 — Final Target State

The final MVP target is:

```text
Bobby's local-first personal assistant
  + delegated Microsoft Graph retrieval
  + source-linked operational memory
  + selective file/work-product ingestion
  + local model extraction and synthesis
  + Obsidian output and review loop
  + launchd morning automation
  + safe diagnostics and evidence
```

The system should reduce administrative overhead without creating a second inbox, uncontrolled document crawler, or opaque model-generated task list. It must remain traceable, controlled, local-first, and ready for future assistant workflows after the MVP proves value.
