# Client Tool Operating Manifest (N8C-23)

The Client Tool Operating Manifest is a first-class, versioned record of **what tool a connected client
should use, when, in what sequence, and what not to do** — plus a freshness contract so it never
silently drifts from the live tool surface.

## What it contains (`obsidian_mcp/client_tool_manifest.py`)

`build_manifest(tool_index, runtime_commit, now, manifest_version)` enumerates the live registered
tool surface and produces:

- **Per-tool classification** — `tool_class` (read_only / navigation / staged_write /
  canonical_promotion / status / blocked_or_deprecated), `safety_class`, and `read_write_class`
  (read_only / staged_write / canonical_write / blocked). `classify_tool` maps each name/group.
- **Workflow route recipes** — ordered tool sequences for common intents: `document_session`,
  `find_source_file`, `retrieve_decision`, `check_tool_manifest_freshness`.
- **Replacement map** — preferred tool for a given intent over deprecated/blocked alternatives.
- **Negative instructions** — e.g. never invent an approval id, never expect a raw transcript to be
  accepted. (Note: `pa_*` tools **are** gateway-reachable as of the N8C-24 gateway expansion — see the
  "Gateway allowlist change" section below; an earlier "never route `pa_*` through the gateway" instruction
  was superseded and removed.)
- **Freshness block** — checksum, `generated_from_runtime_commit`, `staleness_state`, review cadence.

`render_manifest_md` renders the human-readable card. Content is organization-neutral.

## Freshness (`ClientToolManifestRepository.freshness_check`)

Compares the current registered tool set against the stored `pa_tool_manifest_entries`:

- `tool_manifest_missing_tools` — tools now live but absent from the manifest.
- `tool_manifest_extra_tools` — tools in the manifest no longer live.
- `tool_manifest_stale` / `staleness_state` — true/`stale` when there is drift or no active manifest.
- `review_required` — set when drift is detected.

`hb_mcp_status` surfaces `client_tool_manifest_*` fields (enabled, version, staleness_state,
review_required, counts) and never crashes when the manifest table/files are absent.

## Refresh is staged, never silent (amendment #6)

Writing the manifest to `99 System/Manifests` is a two-step, reviewed operation:

1. `pa_tool_manifest_refresh_stage` builds a candidate manifest, computes the freshness diff, records a
   `pa_tool_manifest_refresh_proposals` row, and **mints an operator approval id**. It writes nothing
   to the vault (`writes: false`).
2. `pa_tool_manifest_refresh_promote` requires that server-minted approval id (a forged id is rejected
   with `operator_approval_mismatch`), then materializes
   `client-tool-operating-manifest.{md,json}` and records the promotion. There is no code path that
   rewrites the manifest without a staged proposal + approval.

## Tools

Read-only: `pa_tool_manifest_get`, `pa_tool_manifest_tool_help`, `pa_tool_manifest_workflow_get`,
`pa_tool_manifest_freshness_check`. Advisory: `pa_tool_manifest_review_plan`. Staged:
`pa_tool_manifest_refresh_stage`. Approval-gated write: `pa_tool_manifest_refresh_promote`.

Gate: `HB_MCP_CLIENT_TOOL_MANIFEST` (default-on kill-switch).

## N8C-24 generated-output tools

The Client Tool Operating Manifest classifies the 10 `pa_output_*` tools (see
[n8c-24-client-output-workspace](n8c-24-client-output-workspace.md)): `pa_output_stage` /
`pa_output_commit` / `pa_output_archive_commit` as `staged_write`; the seven reads as `read_only`. Clients
should use `pa_output_*` for generated DOCX/XLSX/PDF/PPTX/ZIP work products — **not** the Obsidian vault
tools, **not** canonical artifact promotion, and **not** the legacy `hb_output_*` scratch writer (mapped
deprecated → replaced-by `pa_output_*`). Generated files go only to the `outputs` root; output staging
precedes final save.

## File access: two-tier guidance (clients)

Two distinct file-access tiers exist; use the right one:

- **Folder traversal / structure** — `hb_root_list` (and `hb_root_stat`) for deterministic directory
  navigation over the `home`/`work`/`vault`/`outputs` roots. Use this to browse, not to search.
- **Content search** — `assistant_source_file_search` over the indexed source corpus (FTS). This is the
  primary search path; the legacy `hb_root_search` is a low-level fallback only (weak/no content index) and
  must **not** be the first choice.
- **Reads** — `assistant_source_file_read` for indexed source files, by `source_ref` (preferred; taken
  from a search/list result) or `source_id` — **never an absolute path**. Two modes:
  - `mode="excerpt"` (default): a bounded extract (live when the root is trusted, else the indexed
    `indexed_excerpt_fallback`). Binary/office files return a bounded excerpt.
  - `mode="complete"`: a **complete-or-explicit-failure** read of a supported format —
    txt/md/csv/json/xml/html/log read whole; pdf/docx/xlsx/eml extracted in a bounded, subprocess-isolated
    worker. It never truncates and calls the result complete. Read the response's `retrieval_state`
    (`complete` | `partial` | `too_large` | `unsupported_format` | `archive_not_expanded` | `unavailable`
    | `denied` | `stale` | `moved` | `parser_timeout` | `parser_failed` | `parser_resource_exceeded` |
    `parser_output_too_large`), `content_state`, and `completeness_state` — only `complete` carries whole
    trusted content. **XER/P6 and archives are explicitly unsupported/not-expanded** (never invent their
    content). An old `source_ref` for a renamed file returns `moved` with a `successor_source_ref`.
  The legacy `hb_root_read_excerpt` denies binary content and takes no `source_ref`.

Rule of thumb: **map with `assistant_source_*_map` / folder tools, search and read with `assistant_source_file_*` (hand off the `source_ref` from a search hit to `assistant_source_file_read`), traverse low-level with `hb_root_*` only as fallback.**

## Three-tier file access (updated)

1. **Structure map (default-ON)** — `assistant_source_root_map`, `assistant_source_folder_map`,
   `assistant_source_folder_summary`, `assistant_source_project_map`, `assistant_source_query_plan`,
   `assistant_source_index_health` for project/folder navigation and trust checks.
2. **Content search/read** — `assistant_source_file_search` / `metadata` / `read` over the indexed file corpus.
3. **Legacy root traversal** — `hb_root_list` / `hb_root_stat` only when structure map is empty or operator needs raw FS browse.

Generated outputs: use `pa_output_*` or **`assistant_output_*` aliases** (same handlers). Archive sets
`status=archived` and `destination_state=archived`.


## Creating intelligence artifacts (template-based)

Structured-intelligence artifacts are created as **template-based Obsidian markdown**, not DB records. Use
`pa_artifact_author` (`artifact_type` ∈ decision / person_note / company_note / project_context /
source_card_annotation): it instantiates the matching vault template into the resolved taxonomy folder,
fills `{{title}}` + optional `variables`/`sections`, injects canonical frontmatter, and redacts/caps
content. It has its own write gate and writes only in-taxonomy vault folders. The staged DB pipeline
(`pa_session_capture_stage` → proposal → promotion) does not persist on the read-only-DB serve profile; on
that profile its write steps fail closed with `read_only_db_surface` — prefer `pa_artifact_author`.

## Gateway allowlist change (N8C-24, operator-authorized)

The N8C-22 helper gateway (`hb_assistant_tool_query`) allowlist was deliberately expanded beyond the
canonical assistant set to reach every write surface:
`GATEWAY_ALLOWLIST = ALL_ASSISTANT_TOOLS ∪ pa_artifact_* ∪ pa_tool_manifest_* ∪ pa_output_* ∪
assistant_output_* ∪ pa_prompt_* ∪ ai_outputs_card_upsert`. Denied tools, raw SQL/shell/exec, root/db
tools, and legacy `hb_output_*` stay rejected; every gateway-routed write still passes the full broker
gate chain. The canonical catalog reports **87** `assistant_*` tools across **14** groups (installed and
client-exposed by default). That is the prior 85-tool universe **plus** `assistant_source_index_health`
and `assistant_source_query_plan` on `source_connector`. The 14th group `source_structure` (7 read-only
map/route tools) is **default-ON** (kill-switch `HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0`). Write surfaces
(`pa_*` / `assistant_output_*` aliases / AI outputs) appear as separate catalog sections and are **not**
part of the 87.

## Workflow layers vs N8C contracts

The manifest publishes **15 prompt-preflight workflow recipes** (routing intents with tool sequences).
Separately, N8C exposes **11 workflow contract types** via `assistant_list_workflows` /
`assistant_route_workflow` for consumption classification. See the workflow-layer table and alias map in
[prompt-preflight-tool-routing](prompt-preflight-tool-routing.md#workflow-layers-§12--two-complementary-surfaces).

## Mandatory MCP tool-surface maintenance

Any change to the MCP tool surface must update this manifest, the catalog/help/query gateway, and the
prompt preflight routing (families / workflows / tool entries / freshness). The 10-step checklist and the
guard tests that enforce it live in the root [AGENTS.md](../../AGENTS.md); see also
[mcp-tool-surface-maintenance](mcp-tool-surface-maintenance.md),
[prompt-preflight-tool-routing](prompt-preflight-tool-routing.md), and
[tool-routing-freshness-policy](tool-routing-freshness-policy.md).
