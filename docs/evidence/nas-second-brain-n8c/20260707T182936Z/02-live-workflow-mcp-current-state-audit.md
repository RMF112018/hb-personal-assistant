# 02 — Current-state audit (before N8C-16)

N8C-15 gave the workflow contract/router a local CLI + read-only GET API surface, but **no remote MCP
tool**. Live LLM/MCP clients (ChatGPT etc.) had to call many lower-level N8C tools by hand to assemble
routing/context. N8C-16 closes that gap by exposing the router as six bounded read-only MCP tools — while
staying strictly inside the N8C read-only remote posture (no build/apply/answer/action tool, one sanctioned
remote write). It does NOT advance workflow implementation (N8C-17), action staging (N8C-18), or the
operator UI (N8C-13).
