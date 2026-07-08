# Client Generated-File Output Policy (N8C-24)

Policy governing what connected clients may write as generated files, where, and under what controls.

## Allowed vs denied

**Allowed generated extensions:** `txt md csv json docx xlsx pptx pdf html zip`.

**Always denied** (executable/script/credential): `sh command app exe dmg pkg py js ts jar bat ps1 ps
sqlite db pem p12 key enc`. Enforced in `resolve_output_relative_path` / `validate_output_extension` and by
the `denied_output_extensions` config set.

## Content modes

`text`, `markdown_text`, `csv_text`, `json_text`, `html_text`, `base64_binary`,
`docx_from_markdown_or_text`, `xlsx_from_csv`, `pptx_from_markdown_or_json`, `pdf_from_html_or_markdown`,
`zip_base64`, `zip_from_outputs`. Every format is generated for real (python-docx / openpyxl / python-pptx /
reportlab / stdlib zipfile). **No format is faked** — a renderer that cannot produce a valid file raises
rather than writing a placeholder.

## Destination rules

- Files write only under the `outputs` root, in the controlled folders `00 Pending`, `01 Final`,
  `90 Archive`, `99 Receipts`, `99 Manifests`. Any other top-level segment is rejected.
- No path traversal, absolute paths, hidden/protected segments, or symlink escapes
  (`path_safe` + `deny_if_blocked`).
- No default overwrite: a colliding destination is refused (the operator re-stages a new version).
- Generated files never write to the Obsidian vault or any canonical location.

## Approval + idempotency

Commit requires a **server-minted** `operator_approval_id` (from staging) and the server-derived
idempotency key. A client cannot invent either. Commit recomputes the staged content hash and fails closed
on drift. Retries are idempotent.

## Size + rate limits

`max_client_output_file_bytes` (25 MiB), ZIP member/uncompressed caps, and a per-window write budget bound
every write. Oversized payloads are rejected before any file is written.

## Relationship to other write surfaces

- **AI Outputs** (`ai_outputs_card_upsert`): markdown cards into the vault AI Outputs folder — unchanged and
  separate.
- **N8C-23 canonical promotion**: decisions/preferences/workflows → Obsidian cards. A generated file is not
  canonical memory unless separately promoted.
- **Legacy scratch writer** (`hb_output_write_file`): internal/local only, hard-denied remotely, and mapped
  deprecated → replaced-by `pa_output_*` in the Client Tool Operating Manifest.

## Mandatory MCP tool-surface maintenance

Any change to the `pa_output_*` tools (added/removed/renamed/argument/output/safety/family change) requires
updating the Client Tool Operating Manifest, the catalog/help/query gateway allowlist, the prompt preflight
routing, freshness checks, and tests — see [mcp-tool-surface-maintenance](mcp-tool-surface-maintenance.md).
