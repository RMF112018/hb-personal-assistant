# 03 — Safe-Root + Tool-Scope Inventory (with the N8B lockdown)

## Roots (unchanged from N7)
`vault` RW, `outputs` RW, `home`/`work` RO, DB RO. Path-safe FS + denied name/dir patterns (`nas_mcp/config.py`); host-path leak guard scrubs `/volumeN/...`.

## Capability-split write gates (NEW — `nas_mcp/profile.py`)
Three **independent** gates, never one broad flag:
| Gate | Tools | `remote_cloudflare` | `local_trusted` |
|---|---|---|---|
| `ai_outputs` | `ai_outputs_card_upsert` | **allowed** | allowed |
| `local_scratch_output` | `hb_output_write_file`, `hb_output_create_dir` | **hard-denied** | allowed |
| `legacy_broad_vault` | `create_note`, `patch_note`, `vault_update_frontmatter`, `vault_create_note_from_template`, `vault_append_to_daily_note` | **hard-denied** | allowed |

In `remote_cloudflare` the scratch + legacy gates are **hard-denied regardless of any env override** (`profile.scratch_output_write_enabled`/`legacy_vault_write_enabled` return `False` before consulting overrides) — a stray flag can never re-open broad writes on the internet-facing surface.

## Effect on the tool surface
- **Blocked write tools** are (a) absent from the registered tool list (`tool_registration.py`: output writers + `ai_outputs_card_upsert` are conditionally registered; the 5 vault-write tools are subtracted from the enabled obsidian set) AND (b) denied+audited at the broker if invoked directly (`broker.dispatch` → `write_tool_blocked_by_profile:<tool>`).
- `hb_mcp_status` reports `exposure_profile`, `blocked_write_tools`, and the filtered `obsidian_tools_enabled` / `obsidian_tools_blocked`.

## Tier mapping (remote_cloudflare)
- Tier 0 (health/status): `hb_mcp_status` — allowed.
- Tier 1 (read second-brain): `hb_db_select` (allowlisted), vault intelligence/metadata/graph/email read tools — allowed.
- Tier 2 (bounded file reads): `hb_root_*`, `read_file` — allowed.
- Tier 3 (output write): **`ai_outputs_card_upsert` only** — allowed; scratch output writers denied.
- Tier 4 (vault mutation / ingestion / drains / watcher): denied (5 vault-write tools blocked here; ingestion/index/summarize already in `NAS_OBSIDIAN_BLOCKED`).
- Tier 5 (admin/destructive: raw SQL, shell, arbitrary FS, secret reads): never registered; `DENIED_TOOL_NAMES` + denied dir/name patterns.

## Verdict
The internet-facing (`remote_cloudflare`) surface is provably **read (tiers 0-2) + the single AI Outputs write (tier 3)**; tiers 4-5 denied. Proven by `tests/test_nas_mcp_remote_profile.py` (`29`).
