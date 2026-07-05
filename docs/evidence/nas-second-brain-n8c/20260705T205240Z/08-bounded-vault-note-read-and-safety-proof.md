# 08 — Vault-Note Read: Complete Content + Path Safety Proof

`assistant_get_vault_note` / `GET /api/assistant/vault-note` return **complete, unredacted** note
content by **intentional operator decision** (deep content is the point — see `02`), wrapping
`tools.read_file` + `tools.resolve_safe_path` + `pathsafe.path_blocked`, with the read caps raised (via
`config.model_copy`) to a high absolute ceiling (`ASSISTANT_MAX_CONTENT_CHARS` ≈ 2,000,000 chars;
`max_file_bytes` raised) so a normal note comes back whole — not truncated. N8C-3 deliberately does NOT
add a broad redaction layer that would destroy normal personal/work content utility; deep content is
tool-mediated and bounded, not unrestricted. (Content is still bounded by the absolute ceiling and
path-safety; only `md/txt/pdf/docx` are read — raw `.eml` is not exposed.)

## Complete content
- Service `test_get_vault_note_complete_content`, API `test_vault_note_complete_content`, MCP
  `test_assistant_vault_note_complete_and_unredacted`: return the full note (`file_type="md"`,
  non-empty `content`, `metadata.truncated=False`). No PII masking is applied by the nav layer.

## Path safety (conservative, clarification #5)
`test_get_vault_note_rejects_traversal_absolute_nul_hidden` + `test_get_vault_note_rejects_symlink_escape`
(service), `test_vault_note_traversal_400` (API):
- **absolute** path → rejected (`absolute_paths_not_allowed`).
- **`..` traversal** → rejected (`path_traversal_not_allowed`).
- **NUL byte** → rejected (`nul_byte_in_path`, explicit guard).
- **protected/hidden folders** (`.obsidian`, `.hidden`, …) → rejected (`protected_path_blocked`;
  `pathsafe.PROTECTED_SEGMENTS` + dotfile rule, `include_hidden=False`).
- **symlink escape** → rejected: `resolve_safe_path` canonicalizes with `.resolve()` and re-checks
  `relative_to(vault_root)`, so a symlink pointing outside the vault fails containment
  (`path_outside_vault_root`). Proven by creating a symlink to a file outside the vault and asserting
  the read raises.
- No raw `.eml` path: `get_vault_note` reads only `config.allowed_file_types` (md/txt/pdf/docx) via
  `read_file`; raw `.eml` is a different tool, not exposed here.

## Result
All pass. Complete content returned; every unsafe path class rejected before any read.
