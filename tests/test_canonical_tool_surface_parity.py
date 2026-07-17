"""Canonical authority parity — fail on contradictory multi-source metadata."""

from __future__ import annotations

import os
import tempfile

from hb_assistant.obsidian_mcp.canonical_tool_specs import classify_tool, replacement_map
from hb_assistant.obsidian_mcp.client_tool_manifest import REPLACEMENT_MAP, WORKFLOW_RECIPES
from hb_assistant.obsidian_mcp.client_tool_manifest import classify_tool as cm_classify
from hb_assistant.obsidian_mcp.tool_family_manifest import FAMILY_IDS, family_for_tool
from hb_assistant.obsidian_mcp.workflow_recipe_manifest import WORKFLOW_IDS, WORKFLOWS


def test_classify_tool_is_single_authority() -> None:
    for name in ("pa_prompt_route", "assistant_source_root_map", "pa_output_stage", "hb_db_select"):
        assert classify_tool(name, None) == cm_classify(name, None)


def test_replacement_map_is_single_authority() -> None:
    assert dict(REPLACEMENT_MAP) == replacement_map()


def test_workflow_recipes_are_projection_of_published_workflows() -> None:
    """WORKFLOW_RECIPES is a list projection of WORKFLOWS with publish_to_client_manifest."""
    published = [w for w in WORKFLOWS if w.get("publish_to_client_manifest")]
    names = {r["workflow_name"] for r in WORKFLOW_RECIPES}
    assert names == {w["workflow_id"] for w in published}
    assert names <= set(WORKFLOW_IDS)
    # No unpublished workflow appears.
    unpublished = {w["workflow_id"] for w in WORKFLOWS if not w.get("publish_to_client_manifest")}
    assert names.isdisjoint(unpublished)
    by_id = {w["workflow_id"]: w for w in WORKFLOWS}
    for r in WORKFLOW_RECIPES:
        assert r["tool_sequence"] == list(by_id[r["workflow_name"]]["tool_sequence"])
    # Client capability coverage (at least one each).
    cats = {by_id[n].get("client_capability_category") for n in names}
    for needed in (
        "session_capture",
        "source_search",
        "source_map",
        "generation",
        "decision",
        "manifest",
        "vault_read",
        "preference",
        "open_loop",
        "staging",
        "promotion",
        "surface_audit",
        "mixed_retrieval",
    ):
        assert needed in cats, needed
    assert len(names) >= 15


def test_every_workflow_tool_has_family() -> None:
    for w in WORKFLOWS:
        for tool in w["tool_sequence"]:
            assert family_for_tool(tool, None) in FAMILY_IDS, (w["workflow_id"], tool)


def test_live_surface_includes_routing_and_classifies() -> None:
    from hb_assistant.nas_mcp.artifact_tools import current_tool_names
    from hb_assistant.nas_mcp.config import NasMcpConfig
    from hb_assistant.store.migrator import SQLiteMigrator

    d = tempfile.mkdtemp()
    db = os.path.join(d, "t.db")
    SQLiteMigrator(db_path=db).apply()
    cfg = NasMcpConfig.from_mapping({"db_path": db, "roots": {"outputs": {"path": d, "mode": "read_write"}}})
    cfg.capability_profile = "legacy-v12"
    names = current_tool_names(cfg)
    assert "pa_prompt_route" in names
    for n in sorted(names)[:50]:
        assert family_for_tool(n, None) in FAMILY_IDS
        tc, sc, rw = classify_tool(n, None)
        assert tc and sc and rw


def test_bootstrap_flags_default_disabled() -> None:
    import inspect

    from hb_assistant.nas_mcp import artifact_tools

    src = inspect.getsource(artifact_tools.bootstrap_persisted_manifest)
    assert 'os.environ.get("HB_MCP_MANIFEST_FIRST_INSTALL_AUTOPROMOTE", "").strip() == "1"' in src
    assert 'os.environ.get("HB_MCP_MANIFEST_AUTO_STAGE_ON_DRIFT", "").strip() == "1"' in src
    # Default empty string → disabled
    assert '== "1"' in src
