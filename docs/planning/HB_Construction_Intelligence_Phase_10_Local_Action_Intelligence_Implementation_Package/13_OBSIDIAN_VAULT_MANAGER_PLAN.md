# 13 Obsidian Vault Manager Plan

## Purpose

Use Obsidian as a durable local knowledge/output layer without allowing uncontrolled note rewriting.

## Target vault location

User stated intended output folder:

`~/Obsidian Vault/Work/Daily-Brief/`

The local agent must reconcile this with current config defaults and update config/examples accordingly, without breaking existing vault path behavior.

## Build capabilities

- `hb-assistant vault status --json`
- `hb-assistant vault index --dry-run --json`
- `hb-assistant vault write-daily-brief --date YYYY-MM-DD --dry-run --json`
- `hb-assistant vault suggest-tags --dry-run --json`
- `hb-assistant vault update-managed-section --note <path> --section <id> --dry-run --json`

## Write policy

- Create notes only in allowlisted folders.
- Update only HB-managed marker blocks.
- Merge only allowlisted frontmatter keys.
- Preserve unrelated user frontmatter and body text.
- Preserve checkbox state where stable keys match.
- Never copy source documents into the vault.
- Never persist raw restricted content.

## Suggested folders

- `Work/Daily-Brief/`
- `Work/Projects/`
- `Work/Actions/`
- `Work/Meetings/`
- `Work/References/`
- `Work/AI-Outputs/`
- `Work/MCP-Packets/`
