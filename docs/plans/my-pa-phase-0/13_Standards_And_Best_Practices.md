# Standards and Best Practices

Prepared: 2026-05-25

## Standards

- Python 3.12+, pytest, ruff, mypy.
- Pydantic/JSON Schema for config and model outputs.
- Central Graph client; no ad hoc requests.
- SQLite migrations are idempotent.
- Foreign keys and WAL enabled.
- Metadata before download.
- Dry-run before writes.
- Source links required.
- Marker-bounded Obsidian writes.
- Local Ollama by default.
- Central redactor for logs/evidence.
- Phase-end evidence required.


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
