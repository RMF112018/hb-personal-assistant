# 05 — Output write sandbox tools

## Root mapping

| Host path | Container mount | Mode |
|---|---|---|
| `/volume1/homes/bfetting/mcp-outputs` | `/mnt/outputs` | read_write |

## Tools

Implemented in `src/hb_assistant/nas_mcp/output_tools.py`:

| Tool | Access |
|---|---|
| `hb_output_list` | read |
| `hb_output_stat` | read |
| `hb_output_read` | read |
| `hb_output_write_file` | write |
| `hb_output_create_dir` | write (mkdir only) |

Root fixed to **`outputs`**; no `root_key` parameter on write tools.

## Write rules

- Extension allowlist: `.txt`, `.md`, `.csv`, `.json`, `.yaml`, `.yml`, `.docx`, `.xlsx`
- `overwrite=False` default; explicit `overwrite=True` required to replace
- Max size: `max_output_file_bytes` (default 1_048_576)
- Parent dirs created only under `/mnt/outputs`
- **No delete tool** — `hb_output_delete` in broker deny list
- Traversal/absolute path guards same as other roots

## Write implementation

`src/hb_assistant/nas_mcp/file_writers.py`:

- Plain text formats written directly
- `.docx` via `python-docx`
- `.xlsx` via `openpyxl` (CSV-shaped content input)
- PDF write **not implemented** (deferred)

## Audit on writes

Broker records: `write_attempted`, `write_allowed`, `overwrite_requested`, `overwrite_applied`, `sha256_prefix` (12 hex chars), `file_type`.

## Local test evidence

| Test | Result |
|---|---|
| `test_output_sandbox_writes` | PASS — txt/md/csv/json write; `.exe` denied; overwrite false blocks; overwrite true succeeds; audit JSONL present |
| `test_vault_write_outside_vault_denied` | PASS — `../../vault/` traversal from outputs denied |

## NAS functional proof

**Deferred.** Host directory **`/volume1/homes/bfetting/mcp-outputs` now exists** (operator-created post-session). MCP re-apply and live output write probes still blocked pending passwordless sudo to runner. See `10-nas-reapply-proof.md`.
