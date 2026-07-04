# 02 — Source Vault Inventory (redacted)

Live source vault `<mac-obsidian-vault>` (= the Mac `Documents/Obsidian Vault`), enumerated read-only. **No note
bodies or file contents were read or printed — counts and structure only.**

| Metric | Value |
|---|---|
| All files (incl `.DS_Store`) | 230 |
| `.DS_Store` files | 9 |
| **Files excluding `.DS_Store`** | **221** |
| **Markdown notes** | **155** |
| Directories | 63 |
| Symlinks | 0 |
| Total size (excl `.DS_Store`) | 4,446,272 B (~4.24 MiB) |
| Files > 5 MB | 0 |

## Notes on the mirror set
- `.DS_Store` (macOS Finder metadata) is **excluded** from the mirror — it is noise, not vault content.
- 0 symlinks and 0 large files → a straight tar mirror is safe and small.
- The mirror set is therefore **221 files (155 md + 66 non-md) across 63 directories** = **284 tar entries**
  (221 files + 63 directories).
- Content-safety was established in N5: generated-card frontmatter carries relative `source_path` / `source_root_key`,
  never absolute Mac paths; bodies link by rel_path/source_id. Relocating the vault root is transparent.

Redaction: the absolute Mac vault path is shown as `<mac-obsidian-vault>`; no filenames, note titles, or bodies appear.
