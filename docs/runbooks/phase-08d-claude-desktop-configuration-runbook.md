# Phase 08D — Claude Desktop MCP Configuration Runbook (Operator)

**Audience:** Bobby (operator). **Posture:** local-first, read-only, stdio-only, advisory.
**Hard rule:** the assistant **never writes or overwrites the live Claude Desktop config
automatically**. It only generates a *preview* you copy in by hand after it validates.

This runbook wires the local Phase 08D MCP bridge into Claude Desktop. The bridge exposes
**workflows only** (nine allowed tools, five resources, five prompts) — never raw stores,
arbitrary SQL, direct Graph/Procore, email/calendar mutation, source-system writeback, raw
payloads, signed/download URLs, raw prompts/responses, or final determinations.

> Note: stdio serving is **fail-closed** until the Phase 08D guard proofs (Prompts 13/14)
> and the optional `mcp` SDK (`pip install -e .[mcp]`) are in place. Use this runbook to
> stage the config; `mcp serve` will start serving once those land.

---

## Operator steps

1. **Generate the preview**
   ```bash
   hb-assistant second-brain mcp config-preview --client claude-desktop --json
   ```
   This writes a preview to
   `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/claude-desktop-config-preview.json`
   and persists a metadata-only snapshot row. It does **not** touch the live Claude config.

2. **Verify it is safe** — confirm the JSON shows:
   - `"safe": true` and `"schema_conformant": true`
   - `"transport": "stdio"`
   - `"unsafe_reasons": []`
   - `"auto_apply": false`
   - `"env_keys": ["HB_MCP_POLICY", "HB_MCP_TRANSPORT"]`

   If any check fails, **stop** — do not paste the config.

3. **Copy the preview into Claude Desktop — manually.** Open the live config file and paste
   the `mcpServers` block from the preview:
   ```
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```
   The assistant never writes this file for you. The block is exactly:
   ```json
   {
     "mcpServers": {
       "hb-personal-assistant": {
         "command": "hb-assistant",
         "args": ["second-brain", "mcp", "serve", "--stdio", "--json"],
         "env": { "HB_MCP_TRANSPORT": "stdio", "HB_MCP_POLICY": "local_safe" }
       }
     }
   }
   ```

4. **Restart Claude Desktop** so it re-reads the config.

5. **Confirm posture**
   ```bash
   hb-assistant second-brain mcp audit --json
   ```
   (Audit surface lands in Prompt 10.) Confirm the reported posture: stdio transport, no raw
   access, no direct Graph/Procore, no writeback/external delivery, metadata-only receipts.

---

## Safe-vs-unsafe checklist

A config preview is **safe** only when all of the following hold:

| Check | Safe value |
|---|---|
| `command` | `hb-assistant` only (no shell / arbitrary binary) |
| `transport` | `stdio` only (no http / sse / websocket / tcp / remote) |
| `args` | exactly `["second-brain","mcp","serve","--stdio","--json"]` |
| `env` keys | only `HB_MCP_TRANSPORT`, `HB_MCP_POLICY` (no secrets/tokens) |
| `env` values | no broad filesystem path; transport stays `stdio` |
| live config | pasted **manually**; never auto-written |

If the preview reports `safe=false`, `unsafe_reasons` names the violation (`unsafe_command`,
`unsafe_args`, `unsupported_transport`, `unsafe_env_key:<k>`, `broad_filesystem_path_in_env`).
Do not proceed.

---

## What this never does

- Never writes or overwrites `~/Library/Application Support/Claude/claude_desktop_config.json`.
- Never adds env secrets, tokens, or broad filesystem grants.
- Never exposes stores, SQL, raw content, direct APIs, writeback, or determinations.
