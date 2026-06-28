# UI Policy Configuration State

The Settings / Obsidian MCP panel now exposes an Autonomous Vault Manager section with:

- write mode enabled/disabled
- autonomous Markdown management enabled/disabled
- max write character limit
- parent folder creation policy
- backup-before-replace policy
- protected path summary
- write readiness check
- write smoke test
- recent mutation events

Default policy values:

```json
{
  "writes_enabled": false,
  "vault_markdown_write_enabled": false,
  "max_write_chars": 120000,
  "write_requires_expected_sha256": true,
  "backup_before_replace": true,
  "create_parent_dirs_enabled": true,
  "allow_full_vault_markdown_writes": true,
  "protected_paths": [".git", ".obsidian", ".trash", ".hb-assistant/backups"],
  "blocked_hidden_paths": true,
  "allowed_write_file_types": ["md"]
}
```

