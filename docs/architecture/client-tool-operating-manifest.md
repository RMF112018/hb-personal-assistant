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
