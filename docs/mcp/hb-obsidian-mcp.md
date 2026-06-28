# HB Obsidian MCP

HB Obsidian MCP is managed from the app UI.

Open **Settings** and use the **Obsidian MCP** panel to:

- confirm or change the vault root
- enable or disable the local MCP service
- run a health check
- inspect the registered tools
- run test directory, search, and file-read actions
- copy the Grok Remote MCP configuration

The Phase 1 service is filesystem-only. Obsidian does not need to be open.

## Settings

The panel shows service state, filesystem mode, vault root, endpoint URL, token status, registered tool count, latest health-check timestamp, blocking issues, and warnings.

Configurable fields are:

- vault root
- enabled state
- local host and port
- bearer token status
- max file size
- max result character limit
- allowed file types
- default scope

Bearer tokens are write-only after save. The UI shows whether a token is configured, but does not render the saved token value.

## Tools

Phase 1 registers:

- `list_directory`
- `search_vault`
- `read_file`

The Settings panel includes test controls for listing, searching, and reading against the configured vault.

## Security

The backend rejects absolute paths, traversal paths, and symlink escapes outside the configured vault root. It enforces file-size and result-character caps and returns truncation metadata for bounded reads.

Phase 1 does not create or patch notes and does not write to source documents.

## Deferred

The following are not part of Phase 1:

- note creation
- note patching
- subcontract analysis
- critical findings generation
- Obsidian REST mode
- register mutation
- starter skills
