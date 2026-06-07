# 03 Raw-Content Architecture

```text
Graph email/calendar live reads
        |
        v
Raw-content normalizers
        |
        v
Local persistence
  - raw email content
  - raw calendar content
  - source refs
  - project matches
  - processing receipts
        |
        v
Backend endpoints
  - include raw fields by default or via include_raw=true
  - redacted mode still available
        |
        v
Local model context builder
  - bounded raw thread/event packets
  - schema-enforced extraction
        |
        v
Reviewable candidates
  - tasks
  - commitments
  - follow-ups
  - meeting prep
  - project relationships
        |
        v
Dashboard / Daily Brief / Obsidian / MCP
```

## Key design choice

Do not rely on the model reading the DB directly. The app should build raw-content packets from local storage and pass bounded packets to Ollama/local model providers.

## Raw-content modes

- `disabled`: current metadata-only behavior.
- `email_calendar`: raw content enabled for email and calendar only.
- `all_supported`: raw content enabled for all implemented source families.
- `all_supported_plus_downstream`: raw content may be included in Obsidian/MCP packet outputs when requested.

Recommended Phase 10A default for the user's machine:

```yaml
raw_content:
  mode: email_calendar
  enabled: true
  default_endpoint_behavior: include_raw
```
