# 22 — Client Compatibility Matrix

Proofs are **HOLD** in this foundation (no live tunnel/Access). A full N8B PASS requires each client path proven or a secure bridge implemented.

| Client | Remote MCP path | Auth | Foundation status | Notes |
|---|---|---|---|---|
| **Claude** (Desktop / Claude Code MCP) | remote HTTP / Streamable HTTP MCP at `https://mcp.bobby-fetting.me/mcp`; custom headers supported | Access service token (header) or OAuth | **design ready, proof HOLD** | Most straightforward first lane — Claude supports remote HTTP MCP + custom headers. |
| **ChatGPT** (Apps/connector) | remote MCP connector | likely DCR/OAuth (the `:8000` OAuth surface already hardened DCR/WWW-Authenticate/CIMD) | **gap to verify, proof HOLD** | Do NOT assume service-token headers suffice; verify the exact ChatGPT connector requirement. If OAuth required, that reinforces the origin-side-auth sub-phase (`19`). |
| **Grok** | not assumed native | service token or **secure bridge** | **bridge design HOLD** | Do not assume native MCP. If Grok lacks remote MCP, design a bridge that does NOT bypass Access or expose raw NAS surfaces. |

## Per-client test template (run at live activation)
Connect → authenticate via Access/token/bridge → list tools → `hb_mcp_status` → data-freshness → search second brain → fetch approved note/summary → `ai_outputs_card_upsert` create → update with expected SHA → attempt raw SQL/FS/secret → confirm denial.

## Rule
Any unsupported client path is **HOLD, not guessed**; no client may require disabling Access or exposing raw NAS surfaces.
