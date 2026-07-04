# 08 — Audit design and proof

## Writer

`src/hb_assistant/nas_mcp/audit.py` — JSONL to `{audit_dir}/mcp-audit-{YYYYMMDD}.jsonl`, mode `0o600`.

## Fields (broker-enriched)

| Field | Source |
|---|---|
| `timestamp_utc` | audit writer default |
| `request_id` | UUID hex per dispatch |
| `tool_name` | broker |
| `actor` | config (`bfetting-via-ssh-launcher`) |
| `root_key` | broker (from args or vault default) |
| `relative_path` | broker (from args) |
| `operation` | tool_name |
| `access_mode` | `read` or `write` |
| `decision` | `allow` or `deny` |
| `deny_reason` | deny path only |
| `duration_ms` | broker |
| `bytes_requested` | (implicit via args; not raw content) |
| `bytes_returned` | allow: from result |
| `rows_returned` | DB/list/search counts |
| `write_attempted` | true for Obsidian writes + output writes |
| `write_allowed` | true on allow path for writes |
| `redaction_applied` | excerpt tools |
| `file_type` | read/write results |
| `overwrite_requested` | output writes |
| `overwrite_applied` | output write result |
| `created_dirs` | output mkdir |
| `sha256_prefix` | output writes (12 hex chars max) |
| `nas_readonly` | true (means no backend/DB writes; not filesystem RO) |
| `client_mode` | `nas_readonly_streamable_http` |

**Never logged:** raw file content, full SHA256, secrets, note bodies.

## Obsidian mutation audit

Mac `mutations.py` writes separate JSONL under `HB_OBSIDIAN_MCP_SUPPORT_DIR` (container: `/app-support/audit/mcp/obsidian-support`). Backups under `/app-support/audit/mcp/obsidian-backups`. Not in vault tree.

## Local proof

| Test | Audit evidence |
|---|---|
| `test_db_select_allowlist_and_denials` | audit file created on allow/deny |
| `test_filesystem_traversal_and_enc_denied` | audit on vault calls |
| `test_output_sandbox_writes` | audit after output writes |

Example path in fixtures: `{tmp_path}/audit/mcp-audit-*.jsonl`

## NAS proof

No NAS audit JSONL captured this session (MCP not running post-change).
