"""Phase 08D local MCP bridge (server foundation + config surface).

Stdio-only, fail-closed, metadata-only. Exposes the server-foundation status, the
Claude Desktop config-preview surface, and the fail-closed serve entrypoint. The tool
broker, workflow wrappers, resources, prompts, and receipts arrive in Prompts 04–08.
"""

from __future__ import annotations

from .config_preview import assess_config_safety, build_claude_desktop_config_preview
from .policy import build_mcp_status, evaluate_startup_checks
from .server import MCPUnavailable, serve_stdio

__all__ = [
    "MCPUnavailable",
    "assess_config_safety",
    "build_claude_desktop_config_preview",
    "build_mcp_status",
    "evaluate_startup_checks",
    "serve_stdio",
]
