# UI Rendered-State Evidence

The Settings page now includes an **Obsidian MCP** panel between Daily Brief and Preferences.

Rendered controls covered by tests:

- Run Health Check
- Enable MCP
- Disable MCP
- Restart MCP service
- Copy Grok MCP config
- Run test directory listing
- Run test search
- Run test file read

Rendered registry entries covered by tests:

- `list_directory`
- `search_vault`
- `read_file`

Token handling covered by tests:

- saved token value is not rendered
- Grok config renders `Bearer <configured-token>` placeholder only
