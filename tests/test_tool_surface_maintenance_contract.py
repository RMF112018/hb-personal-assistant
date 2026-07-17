"""Tool-surface maintenance contract — the live surface stays fully classified + documented.

These are the guard tests the maintenance mandate (AGENTS.md) points at: if someone adds/removes/renames an
MCP tool without updating the routing manifests, one of these fails.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.tool_family_manifest import FAMILY_IDS, family_for_tool
from hb_assistant.obsidian_mcp.workflow_recipe_manifest import WORKFLOWS

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg():
    from hb_assistant.nas_mcp.config import NasMcpConfig
    from hb_assistant.store.migrator import SQLiteMigrator

    d = tempfile.mkdtemp()
    db = os.path.join(d, "t.db")
    SQLiteMigrator(db_path=db).apply()
    config = NasMcpConfig.from_mapping({"db_path": db, "roots": {"outputs": {"path": d, "mode": "read_write"}}})
    config.capability_profile = "legacy-v12"
    return config


def test_every_live_tool_classifies_into_a_known_family(cfg) -> None:
    from hb_assistant.nas_mcp.prompt_routing_tools import current_tool_groups

    groups = current_tool_groups(cfg)
    for name, group in groups.items():
        assert family_for_tool(name, group) in FAMILY_IDS, name


def test_live_surface_is_not_stale(cfg) -> None:
    from hb_assistant.nas_mcp.prompt_routing_tools import live_freshness

    fr = live_freshness(cfg)
    assert fr["stale"] is False, fr["warnings"]
    if fr.get("independent_baseline"):
        assert fr["tool_surface_gateway_current"] is True
    else:
        assert fr["tool_surface_gateway_current"] in (True, None)
    assert fr.get("execution_attestation_ok") is True


def test_every_workflow_tool_is_live_or_routing_layer(cfg) -> None:
    from hb_assistant.nas_mcp.prompt_routing_tools import PROMPT_ROUTING_TOOLS, current_tool_groups

    live = set(current_tool_groups(cfg))
    for wf in WORKFLOWS:
        for tool in wf["tool_sequence"]:
            assert tool in live or tool in PROMPT_ROUTING_TOOLS, (wf["workflow_id"], tool)


def test_agents_md_declares_maintenance_mandate() -> None:
    agents = REPO / "AGENTS.md"
    assert agents.exists(), "AGENTS.md must exist"
    text = agents.read_text(encoding="utf-8").lower()
    assert "mandatory mcp tool-surface maintenance" in text
    for token in ("family", "workflow", "freshness", "gateway", "preflight"):
        assert token in text, token


def test_routing_content_is_org_neutral() -> None:
    # No employer-specific names leak into the routing manifests.
    banned = ("tropical", "procore", "bfetting", "outlook.com")
    for mod in ("tool_family_manifest.py", "workflow_recipe_manifest.py", "tool_entry_manifest.py",
                "prompt_preflight.py", "tool_surface_freshness.py"):
        text = (REPO / "src/hb_assistant/obsidian_mcp" / mod).read_text(encoding="utf-8").lower()
        for b in banned:
            assert b not in text, (mod, b)
