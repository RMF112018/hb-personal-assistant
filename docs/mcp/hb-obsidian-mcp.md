# HB Obsidian MCP

HB Obsidian MCP is managed from the app UI.

Open **Settings** and use the **Obsidian MCP** panel to:

- confirm or change the vault root
- enable or disable the local MCP service
- run a health check
- inspect the registered tools
- run test directory, search, and file-read actions
- copy the Grok Remote MCP configuration

The service is filesystem-only. Obsidian does not need to be open.

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

The MCP server registers:

- `list_directory`
- `search_vault`
- `read_file`
- `create_note`
- `patch_note`

The Settings panel includes test controls for listing, searching, and reading against the configured vault.

## Autonomous Vault Manager

Write mode is controlled from the same Settings panel. When write mode and Markdown management are enabled, authenticated MCP clients can create and replace Markdown notes inside the configured vault policy without per-write approval.

Phase 2 write tools are:

- `create_note`
- `patch_note`

The write policy blocks absolute paths, traversal paths, protected folders, hidden folders by default, symlink paths, symlink escapes, and non-Markdown files. Existing Markdown replacements require a matching SHA-256 value and create an app-managed backup before replacement.

The UI shows write readiness, protected paths, recent mutation events, backup metadata, and a write smoke test. It does not render raw note content.

## Security

The backend rejects absolute paths, traversal paths, and symlink escapes outside the configured vault root. It enforces file-size and result-character caps and returns truncation metadata for bounded reads.

The service writes Markdown notes only when write mode is enabled. It does not write to PDFs, DOCX files, or other source documents.

## Deferred

The following are not part of Phase 2:

- delete note
- rename or move note
- section-level patching
- subcontract analysis
- critical findings generation
- Obsidian REST mode
- register mutation
- starter skills
