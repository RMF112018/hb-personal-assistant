# Final Implementation Plan

Prepared: 2026-05-25

## Objective

Provide a sequenced implementation path for the local code agent to build `hb-personal-assistant` without guesswork.

## Phases

| Phase | Name | Required Outcome |
| --- | --- | --- |
| 0 | Environment, auth, vault, evidence discovery | Prove environment, manifest, cache paths, certificate facts, vault conventions, and delegated Graph readiness. |
| 1 | Repo scaffold and config | Create Python package, CLI, config examples, .gitignore, path policy, tests. |
| 2 | Auth and Graph client | Implement MSAL delegated provider, token classifier, cache manager, Graph client, retry policy. |
| 3 | Graph read models | Implement mail, sent mail, body, calendarView, attachments, file metadata. |
| 4 | SQLite and source links | Implement migrations, repositories, source_records, source_links, run ledger. |
| 5 | Email classification | Implement aliases, body mentions, direct asks, waiting-on-other candidates. |
| 6 | Extraction | Implement action/meeting/file-review schemas, deterministic rules, local model extraction. |
| 7 | Obsidian writer | Implement marker-bounded Daily Brief and optional companion/reference notes. |
| 8 | File ingestion | Implement eligibility gates, downloads, hashes, parsers, failure isolation. |
| 9 | Retrieval | Implement deterministic retrieval, then gated sqlite-vec semantic retrieval. |
| 10 | launchd automation | Implement launchd install/kickstart/uninstall and catch-up-after-wake logic. |
| 11 | Hardening | Run evidence, sensitive scans, mutation lockout checks, closure checklist. |

## Expected Repo Layout

```text
hb-personal-assistant/
  README.md
  pyproject.toml
  .env.example
  .gitignore
  config/
  docs/architecture/
  docs/decisions/
  docs/evidence/
  docs/validation/
  src/hb_assistant/
    cli/
    auth/
    config/
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
  scripts/proofs/
  tests/
  resources/
```

## Key Components

| Component | Responsibility |
| --- | --- |
| PathPolicy | Resolve repo, Application Support, cache, DB, logs, evidence, and vault paths. |
| TokenCacheManager | Separate delegated/app-only caches and enforce 700/600 permissions. |
| TokenClassifier | Classify delegated/app-only/ambiguous tokens and fail closed. |
| GraphHttpClient | Centralize headers, nextLink paging, Retry-After, and sanitized errors. |
| MailClient | Inbound/sent metadata and bounded body retrieval. |
| CalendarClient | calendarView over configured window. |
| DriveItemClient | File metadata and controlled content download. |
| SQLiteMigrator | Apply idempotent migrations. |
| SourceLinkRegistry | Tie every generated output to source records. |
| ParserRouter | Run safe bounded parsers by file type. |
| OllamaClient | Structured JSON extraction and synthesis. |
| MarkerBoundedWriter | Preserve Obsidian user content outside markers. |
| MorningRunOrchestrator | Execute full morning workflow. |
| LaunchdManager | Generate/install/kickstart/remove LaunchAgent. |

## Validation Pattern

```bash
python -m pytest
ruff check .
mypy src
hb-assistant diagnostics env --json
hb-assistant auth status --json
hb-assistant diagnostics graph --safe --json
hb-assistant run morning --dry-run --json
hb-assistant diagnostics scan-sensitive --repo . --json
```


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
