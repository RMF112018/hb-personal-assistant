# MCP Server Endpoints — which server carries which tools

This repo ships **two distinct MCP servers**. They run as different processes, on different ports, behind
different hostnames, with different OAuth stacks and different tool surfaces. A connected LLM client (ChatGPT
/ Claude.ai / Grok) sees **only the tools of the server its connector URL points at.** Pointing a connector at
the wrong host is the most likely cause of "the server says a tool is enabled but my client can't call it."

## The two servers

| | NAS MCP | Obsidian MCP |
|---|---|---|
| Code | `src/hb_assistant/nas_mcp/` (`server.py`) | `src/hb_assistant/obsidian_mcp/` (`mcp_app.py`) |
| FastMCP app name | `hb-nas-mcp` | `hb-obsidian-mcp` |
| Started by | `hb-assistant mcp serve --nas-readonly --streamable-http` (compose `hb-personal-assistant-mcp`, port **8765**) | mounted in the FastAPI backend at `/mcp` (port **8000**) |
| Public host | **`https://nas-mcp.bobby-fetting.me/mcp`** | **`https://mcp.bobby-fetting.me/mcp`** |
| Profile / auth | `remote_cloudflare`, origin bearer + OAuth (`nas.read`/`nas.write`) | OAuth 2.1 PKCE + DCR (`obsidian.read`/`obsidian.write`) |
| Tool surface | **~137 tools**: the 78 canonical `assistant_*`, the 3 `hb_assistant_*` gateway helpers, `pa_prompt_*`, `pa_output_*`, `pa_artifact_*`, `pa_tool_manifest_*`, `ai_outputs_card_upsert`, status/freshness/root/db reads, and NAS obsidian-adapter wrappers | **~56 tools**: vault read/write + summarize/graph/email/domain plan tools. A read-only ChatGPT principal (`chatgpt_readonly_mode`, scope `obsidian.read`) sees only its ~40–43 `obsidian.read`-scoped subset. |
| Has the N8C stack? | **Yes** — all `assistant_*` / `hb_assistant_*` / `pa_prompt_*` / `pa_output_*` live here | **No** — none of those exist on this server |

## Which endpoint a connector should use

- To reach the **second-brain / N8C tool surface** (assistant navigation, artifact workspace, client output
  workspace, prompt preflight, the `hb_assistant_tool_query` gateway): point the connector at the **NAS MCP**,
  `https://nas-mcp.bobby-fetting.me/mcp`.
- To reach **only the Obsidian vault tools**: the Obsidian MCP, `https://mcp.bobby-fetting.me/mcp`.

`hb_mcp_status` is a **NAS-MCP-only** tool. If a client shows `hb_mcp_status` reporting "78 assistant tools
enabled" but cannot call `assistant_*` / `pa_*`, the status view and the connector are describing **different
servers** — repoint the connector at the NAS MCP.

## Host-cutover status (N8B)

The N8B plan intends to move `mcp.bobby-fetting.me` to front the NAS `:8765` container so the historical host
reaches the NAS MCP. That Cloudflare route change is **on HOLD** (see
`docs/evidence/nas-cloudflare-access-n8b/`), so until it lands, `mcp.bobby-fetting.me` still resolves to the
Obsidian MCP. Until the cutover, use the explicit `nas-mcp.bobby-fetting.me/mcp` host for the NAS surface.

## Client tool access on the NAS MCP

The NAS MCP registers all ~137 tools individually **and** exposes the `hb_assistant_tool_query` gateway. A
client that cannot ingest the full manifest (or that caps the number of callable tools) should use the gateway
+ `pa_prompt_route` to reach the rest — see [client-tool-operating-manifest](client-tool-operating-manifest.md)
and [prompt-preflight-tool-routing](prompt-preflight-tool-routing.md).
