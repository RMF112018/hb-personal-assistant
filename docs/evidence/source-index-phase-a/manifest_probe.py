"""Compute the semantic tool-surface checksum + per-source-tool purposes for manifest-drift evidence."""
import json
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from hb_assistant.nas_mcp.artifact_tools import _build_tool_index, _runtime_manifest_build_kwargs
from hb_assistant.nas_mcp.broker import NasMcpBroker, runtime_commit
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp.client_tool_manifest import build_manifest
from tests.n8c23_helpers import make_env

env = make_env(Path(tempfile.mkdtemp()))
register_nas_mcp_tools(FastMCP("probe"), NasMcpBroker(env["config"]))
m = build_manifest(
    _build_tool_index(env["config"], for_manifest=True),
    runtime_commit="FIXED",  # pin so runtime commit never perturbs the checksum
    now="2026-07-10T00:00:00+00:00",
    **{k: v for k, v in _runtime_manifest_build_kwargs().items() if k != "runtime_commit"},
)
out = {"semantic_surface_checksum": m.get("semantic_surface_checksum")}
tools = {}
for e in m.get("entries", []) or m.get("tools", []) or []:
    name = e.get("tool_name") or e.get("name")
    if name in {"assistant_get_source", "assistant_source_file_read", "assistant_source_file_search",
                "assistant_source_files_list", "assistant_source_file_metadata"}:
        tools[name] = e.get("purpose")
out["source_tool_purposes"] = tools
print(json.dumps(out, indent=2, sort_keys=True))
