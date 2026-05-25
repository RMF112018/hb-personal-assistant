# Final Target Architecture

Prepared: 2026-05-25

## Product Definition

**HB Personal Assistant + Work Product Intelligence System** is Bobby's local-first personal assistant for Microsoft 365, local work product, Obsidian, source-linked retrieval, action intelligence, meeting prep, file review support, and future safe assistant workflows.

The Daily Brief is the first assistant workflow, not the system name.

## System Outcomes

| Outcome | Description |
| --- | --- |
| Daily Brief | Morning summary, priority actions, meetings, waiting items, file review queue, and source links. |
| Operational Memory | SQLite source records, actions, links, files, run ledger, and evidence. |
| Work Product Intelligence | Direct asks, commitments, follow-ups, file review, project signals, risk/contract/safety/compliance signals. |
| Source-Linked Retrieval | Deterministic retrieval first; semantic retrieval second; every output tied to source records. |
| Safe Assistant Foundation | CLI workflows, dry-run, local models, no Microsoft 365 mutation. |

## Source Systems and MVP Treatment

| System | Treatment |
| --- | --- |
| Outlook Mail | Delegated Graph read; inbound lookback 5 days; body retrieval bounded. |
| Sent Mail | Delegated Graph read; 7-day lookback for waiting-on-other detection. |
| Outlook Calendar | Primary calendar via calendarView; yesterday/today/next 2 business days. |
| Attachments | Metadata first; selective download only after eligibility gates. |
| OneDrive/SharePoint Files | driveItem metadata; controlled content download; runtime read-only. |
| Obsidian | Primary output to Daily Notes; optional AI Outputs companion; bounded markers. |
| SQLite | Canonical local state under Application Support. |
| Ollama | Local model extraction/synthesis/embeddings; structured outputs. |
| launchd | 5:00 AM America/New_York or first awake after 5:00 AM; weekends manual-only. |

## Component Model

```text
Microsoft 365
  → Auth + Graph Integration
  → Source Normalization
  → SQLite Operational Memory + Source-Link Registry
  → File Cache + Parser Pipeline
  → Local Model Extraction/Synthesis
  → Obsidian Marker Writer
  → Daily Brief / Meeting Prep / File Review / Retrieval Outputs
```

## Local Runtime Layout

```text
~/Library/Application Support/HB Personal Assistant/
  auth/msal-token-cache.bin
  auth/msal-token-cache-app.bin
  config/config.yml
  db/hb-personal-assistant.sqlite
  cache/files/
  cache/extracted-text/
  embeddings/sqlite-vec/
  logs/
  evidence/
```

## Morning Run

```text
launchd or manual CLI
  → load config and validate auth/cache permissions
  → validate delegated token
  → sync mail and calendarView
  → retrieve bounded bodies for mention detection
  → discover attachments/files
  → selectively download/parse eligible files
  → extract actions/prep/waiting/file reviews
  → retrieve local/Obsidian context
  → generate source-linked Daily Brief
  → write marker-bounded Obsidian section
  → persist run ledger and sanitized evidence
```

## Non-Goals

No mail sending, mark-read, categories/flags, calendar mutation, To Do creation, M365 file write-back, tenant-wide crawl, other-user mailboxes, native CAD/Revit parsing, OCR, external LLM dependency, cloud backend, Obsidian plugin UI, or uncontrolled agentic actions.


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
