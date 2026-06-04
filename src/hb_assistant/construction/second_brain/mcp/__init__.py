"""Phase 08D local MCP bridge (server foundation + config surface).

Stdio-only, fail-closed, metadata-only. Exposes the server-foundation status, the
Claude Desktop config-preview surface, and the fail-closed serve entrypoint. The tool
broker, workflow wrappers, resources, prompts, and receipts arrive in Prompts 04–08.
"""

from __future__ import annotations

from .audit import run_mcp_permission_audit, snapshot_all_registries, snapshot_tool_registry
from .broker import DENIAL_REASONS, ToolBroker
from .config_preview import assess_config_safety, build_claude_desktop_config_preview
from .policy import build_mcp_status, evaluate_startup_checks
from .prompts import load_prompts, render_all_prompts, render_prompt
from .proof import (
    build_mcp_allowed_tools_proof,
    build_mcp_claude_desktop_runbook_proof,
    build_mcp_denied_tools_proof,
    build_mcp_prompts_proof,
    build_mcp_resources_proof,
    build_mcp_tool_broker_proof,
)
from .registry import load_allowed_tools, load_denied_actions, load_global_requirements
from .resources import load_resources, read_all_resources, read_resource
from .server import MCPUnavailable, serve_stdio
from .wrappers import build_wrapper_registry


def build_default_broker(*, db_path: str | None = None, persist: bool = True) -> ToolBroker:
    """Construct a broker wired with the nine real workflow wrappers."""
    return ToolBroker(
        wrappers=build_wrapper_registry(db_path=db_path), db_path=db_path, persist=persist
    )


__all__ = [
    "DENIAL_REASONS",
    "MCPUnavailable",
    "ToolBroker",
    "assess_config_safety",
    "build_claude_desktop_config_preview",
    "build_default_broker",
    "build_mcp_allowed_tools_proof",
    "build_mcp_claude_desktop_runbook_proof",
    "build_mcp_denied_tools_proof",
    "build_mcp_prompts_proof",
    "build_mcp_resources_proof",
    "build_mcp_status",
    "build_mcp_tool_broker_proof",
    "build_wrapper_registry",
    "evaluate_startup_checks",
    "load_allowed_tools",
    "load_denied_actions",
    "load_global_requirements",
    "load_prompts",
    "load_resources",
    "read_all_resources",
    "read_resource",
    "render_all_prompts",
    "render_prompt",
    "run_mcp_permission_audit",
    "serve_stdio",
    "snapshot_all_registries",
    "snapshot_tool_registry",
]
