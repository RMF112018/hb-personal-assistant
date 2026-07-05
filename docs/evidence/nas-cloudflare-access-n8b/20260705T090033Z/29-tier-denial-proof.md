# 29 — Tier / Write-Surface Denial Proof

From `tests/test_nas_mcp_remote_profile.py` (6 passed) under `HB_MCP_PROFILE=remote_cloudflare`.

## `test_remote_profile_blocks_all_broad_writes` — PASS
All 7 broad write tools are denied+audited on dispatch:
`create_note`, `patch_note`, `vault_update_frontmatter`, `vault_create_note_from_template`, `vault_append_to_daily_note`, `hb_output_write_file`, `hb_output_create_dir` → each returns `ok=False` with error `write_tool_blocked_by_profile:<tool>`, and an `mcp-audit-*.jsonl` deny event is written.

## `test_remote_profile_ignores_write_overrides` — PASS
With `HB_MCP_ALLOW_LEGACY_VAULT_WRITE=1` and `HB_MCP_ALLOW_SCRATCH_OUTPUT_WRITE=1` set, `create_note` and `hb_output_write_file` are **still denied** — the remote profile hard-locks broad writes regardless of env overrides.

## `test_ai_outputs_is_folder_locked` — PASS
- A traversal title `"../../etc/passwd"` is slugified so the result can only ever be `AI Outputs/…` (never `<tmp>/etc/passwd`).
- A title that slugs to empty (`"///"`) is refused.

## `test_status_reports_profile_and_gates` — PASS
`hb_mcp_status` reports `exposure_profile.profile == "remote_cloudflare"`, `legacy_broad_vault_write_enabled == False`, `local_scratch_output_write_enabled == False`, `ai_outputs_write_enabled == True`; `create_note` appears in `blocked_write_tools` + `obsidian_tools_blocked` and is absent from `obsidian_tools_enabled`.

## `test_local_trusted_profile_reenables_writes` — PASS
Under `HB_MCP_PROFILE=local_trusted`, `create_note` and `hb_output_write_file` succeed — confirming the lockdown is profile-scoped, not a global break.

## Pre-existing denials (unchanged, still enforced)
Raw SQL/shell/exec/absolute-read → `DENIED_TOOL_NAMES`; source ingestion/index/summarize/semantic/LLM-chat/`*_apply` → `NAS_OBSIDIAN_BLOCKED`; secret/token dirs → denied name/dir patterns.

## Verdict
The internet-facing surface denies tiers 4-5 and all broad writes; only read + the folder-locked AI Outputs write remain. **PASS.**
