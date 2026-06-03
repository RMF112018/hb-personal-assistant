"""Phase 08D local MCP bridge (server foundation + config surface).

Stdio-only, fail-closed, metadata-only. Exposes the server-foundation status, the
Claude Desktop config-preview surface, and the fail-closed serve entrypoint. The tool
broker, workflow wrappers, resources, prompts, and receipts arrive in Prompts 04–08.
"""

from __future__ import annotations

from .broker import DENIAL_REASONS, ToolBroker
from .config_preview import assess_config_safety, build_claude_desktop_config_preview
from .policy import build_mcp_status, evaluate_startup_checks
from .proof import build_mcp_tool_broker_proof
from .registry import load_allowed_tools, load_denied_actions, load_global_requirements
from .server import MCPUnavailable, serve_stdio

__all__ = [
    "DENIAL_REASONS",
    "MCPUnavailable",
    "ToolBroker",
    "assess_config_safety",
    "build_claude_desktop_config_preview",
    "build_mcp_status",
    "build_mcp_tool_broker_proof",
    "evaluate_startup_checks",
    "load_allowed_tools",
    "load_denied_actions",
    "load_global_requirements",
    "serve_stdio",
]
