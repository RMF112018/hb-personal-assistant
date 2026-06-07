#!/bin/zsh
set -euo pipefail

cd /Users/bobbyfetting/hb-personal-assistant

export HB_MCP_TRANSPORT=stdio
export HB_MCP_POLICY=local_safe

exec /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant second-brain mcp serve --stdio
