# 13 — Risk & Defer List

## Deferred (intentionally out of N8C-12 scope)
- **`hb://` source resources (N8C-12G)** — deferred. There is no existing `resources.py` / resource pattern
  in `nas_mcp`; adding one now would be net-new surface/risk. The 6 read tools + 6 GET routes fully cover
  discovery/metadata/read. Revisit only if a resource pattern is adopted repo-wide.
- **Live LLM-client testing** — N8C-12 ships a DETERMINISTIC evaluation package (`11`); live client runs are
  a later NAS validation stage.
- **Folder-tree navigation as first-class objects** — listing returns files (keyset-paged) plus advisory
  `child_folders` derived from the current page; a fully paged folder tree is deferred.
- **xlsx/eml live reads** — bounded reads gate on `config.allowed_file_types` (default md/txt/pdf/docx); other
  types fall back to the indexed excerpt. Widening is a config choice, not code.

## Residual risks (low)
- Bounded live reads open original NAS bytes on an internet-exposed surface. Mitigated: single-file open (no
  scan), extension-gated, size-bounded, char-bounded, safe-path-contained, **sensitive roots never
  live-read**, independent kill switch, and always an indexed fallback. Consistent with the N8C-3 intentional
  full-content posture, but narrower (bounded, gated).
- api.py carries pre-existing legacy ruff debt outside the new block; left untouched (surgical).
- The `-q` schedule-canary summary line is not always machine-capturable; greenness rests on exit 0 +
  all-dots + the captured `343 passed`.

## Follow-ups (not blocking)
- A frontend surface over the 6 GET routes (separate UI phase).
- If a future phase needs paged folder trees or resources, build on these read models (no new writes).
