# Security Validation

Validated behavior:

- writes fail when write mode is disabled
- Markdown-only enforcement rejects non-`.md` writes
- full-vault Markdown writes work when policy allows
- `.git`, `.obsidian`, `.trash`, and protected paths are blocked
- hidden paths are blocked by default
- absolute and traversal paths are blocked
- symlink paths and symlink escapes are blocked
- overwrites require SHA-256 protection
- SHA mismatch leaves the existing file unchanged
- backup is created before replacement
- mutation audit events contain metadata only
- MCP responses do not include raw note content

Deferred by design:

- delete note
- rename or move note
- section-level patching
- Obsidian REST mode
- analysis workflows
- register automation
- bulk vault reorganization
- PDF/DOCX/source-file mutation

