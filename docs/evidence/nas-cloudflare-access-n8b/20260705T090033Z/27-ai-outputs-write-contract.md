# 27 — AI Outputs Card Write/Update Contract

Implemented: `nas_mcp/ai_outputs.py` → `ai_outputs_card_upsert`, dispatched via the broker, registered as an MCP tool only when the `ai_outputs` gate is on.

## Contract
```
ai_outputs_card_upsert(
  title: str,
  body_markdown: str,
  tags: list[str] = [],
  source_client: "claude" | "chatgpt" | "grok" | "local" | "unknown" = "unknown",
  expected_sha: str | null = null,
  mode: "create" | "update" | "append" = "create",
)
```

## Controls (all enforced)
- **Folder-locked** to the vault's AI Outputs folder (`config.obsidian.ai_outputs_folder`, default `AI Outputs`). Target rel path is `"<folder>/<slug(title)>.md"`; the slug strips every character outside `[A-Za-z0-9 _-]`, so a traversal-y title can never escape the folder. Extra guards reject `..`, leading `/`, backslash, NUL, over-length, or a first path segment ≠ the folder.
- **Markdown only** — the tool writes a rendered Markdown card (frontmatter + body); no other extension is possible.
- **Size caps** — body ≤ 256 KiB; title ≤ 120 chars; rel path ≤ 200 chars.
- **SHA-gated update** — `mode="update"` requires `expected_sha`; a missing or mismatched SHA is refused (reuses `mutations.patch_note` optimistic concurrency → `sha256_mismatch`).
- **Create-once** — `mode="create"` refuses if the card already exists (`note_already_exists`).
- **Append** — `mode="append"` optimistically appends (optional `expected_sha` guard); creates the card if missing.
- **Backup before overwrite** — via `mutations` `backup_before_replace` (old file copied to `backups/<stamp>/`).
- **Mutation receipt** — every write records to `mutations.jsonl` with actor/`source_client` (`principal_kind`), `tool_name=ai_outputs_card_upsert`, relative path, old/new SHA + bytes, backup path, timestamp, result.
- **Denied targets** — because the path is always `AI Outputs/<slug>.md`, writes to source notes, templates, private folders, raw source roots, generated cards outside AI Outputs, DB paths, and token/secret folders are structurally impossible; the underlying `mutations` engine additionally rejects protected/hidden/symlink paths.

## Reuse
Composes the existing gated engine (`obsidian_mcp/mutations.create_note` / `patch_note`, `sha256_file`) — no re-implementation of SHA/backup/receipt/atomic-write.

## Verdict
Contract implemented and proven by `28` (create/update/append) and `29` (denials).
