"""UI-managed Obsidian MCP foundation.

The public operator surface for this package is the FastAPI/React Settings UI.
No user-facing Typer command group is provided.
"""

from .config import ObsidianMcpConfig, ObsidianMcpConfigPatch
from .service import ObsidianMcpService
from .tools import ObsidianMcpToolError

__all__ = [
    "ObsidianMcpConfig",
    "ObsidianMcpConfigPatch",
    "ObsidianMcpService",
    "ObsidianMcpToolError",
]
