"""NAS read-only MCP server (Phase N7).

Dedicated loopback HTTP MCP — not coupled to the FastAPI backend or Obsidian MCP.
"""

from .server import NasMcpUnavailable, serve_nas_readonly_streamable_http

__all__ = ["NasMcpUnavailable", "serve_nas_readonly_streamable_http"]
