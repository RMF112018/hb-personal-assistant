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
  accepted, never route `pa_*` tools through the assistant gateway.
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

## Gateway allowlist change (N8C-24, operator-authorized)

The N8C-22 helper gateway (`hb_assistant_tool_query`) allowlist was deliberately expanded beyond the
canonical 78 to reach every write surface: `GATEWAY_ALLOWLIST = 78 ∪ pa_artifact_* ∪ pa_tool_manifest_* ∪
pa_output_* ∪ ai_outputs_card_upsert`. Denied tools, raw SQL/shell/exec, root/db tools, and legacy
`hb_output_*` stay rejected; every gateway-routed write still passes the full broker gate chain. The
canonical catalog still reports exactly 78; the write surfaces appear as separate catalog sections.

## Mandatory MCP tool-surface maintenance

Any change to the MCP tool surface must update this manifest, the catalog/help/query gateway, and the
prompt preflight routing. See [mcp-tool-surface-maintenance](mcp-tool-surface-maintenance.md) (created in
the Prompt Preflight phase) and the root `AGENTS.md`.
