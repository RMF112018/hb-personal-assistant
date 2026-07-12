"""NAS MCP tool annotations — read-only / destructive hints on the live FastMCP surface.

A connected client's platform safety layer uses each tool's MCP ``ToolAnnotations`` (``readOnlyHint`` /
``destructiveHint``) to tell safe reads from writes. The NAS MCP previously registered every tool bare
(no annotations), so a client saw a visibly write-capable ~160-tool surface with no read/write signal
and conservatively gated even genuinely read-only tools (e.g. ``pa_prompt_route``). These tests prove
that after registration EVERY tool carries an annotation, that the read/write split exactly mirrors the
broker's own ``_access_mode`` write classification (plus the gateway write proxy), and that the full
inventory is still present (annotations are additive metadata — no tool dropped, no gate changed).

Built against the REAL FastMCP surface — the same object whose ``tools/list`` a connected client calls.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.exposure_audit import _build_surface
from hb_assistant.nas_mcp.tool_registration import _is_write_tool
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture(scope="module")
def surface() -> dict[str, object]:
    """Real FastMCP tool surface over a fresh migrated temp DB (never touches production)."""
    tmp = tempfile.TemporaryDirectory(prefix="nas-annotations-")
    db = str(Path(tmp.name) / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _broker, tools = _build_surface(db)
    try:
        yield tools
    finally:
        tmp.cleanup()


def test_every_registered_tool_is_annotated(surface: dict[str, object]) -> None:
    """No tool is left bare — a missing annotation is exactly the gap that caused the client block."""
    unannotated = [name for name, tool in surface.items() if tool.annotations is None]
    assert not unannotated, f"tools missing ToolAnnotations: {sorted(unannotated)}"
    assert len(surface) > 100, "surface unexpectedly small — registration likely broke"


def test_read_write_split_mirrors_broker_access_mode(surface: dict[str, object]) -> None:
    """Each tool's annotation flags match its ``_is_write_tool`` classification (which mirrors the
    broker's ``_access_mode``): reads are read-only + non-destructive, writes are the inverse."""
    for name, tool in sorted(surface.items()):
        ann = tool.annotations
        assert ann is not None, name
        write = _is_write_tool(name)
        assert ann.readOnlyHint is (not write), (name, "readOnlyHint", ann.readOnlyHint, write)
        assert ann.destructiveHint is write, (name, "destructiveHint", ann.destructiveHint, write)


def test_all_known_write_tools_are_marked_destructive(surface: dict[str, object]) -> None:
    """Regression guard: the concrete write tools present on the surface must every one be destructive.
    Locks the write set so a future tool that mutates state cannot silently register as a safe read."""
    expected_writes = {
        "ai_outputs_card_upsert",
        "assistant_output_archive_commit",
        "assistant_output_cancel",
        "assistant_output_commit",
        "assistant_output_stage",
        "hb_assistant_tool_query",
        "pa_artifact_author",
        "pa_artifact_promotion_apply",
        "pa_artifact_promotion_validate",
        "pa_artifact_proposal_review",
        "pa_artifact_proposal_revise",
        "pa_artifact_proposal_stage",
        "pa_output_archive_commit",
        "pa_output_cancel",
        "pa_output_commit",
        "pa_output_stage",
        "pa_session_capture_stage",
        "pa_tool_manifest_refresh_promote",
        "pa_tool_manifest_refresh_stage",
    }
    present = expected_writes & set(surface)
    assert present == expected_writes, f"expected write tools missing from surface: {expected_writes - present}"
    actual_writes = {
        name for name, tool in surface.items() if tool.annotations and tool.annotations.destructiveHint
    }
    assert actual_writes == expected_writes, (
        f"unexpected destructive: {actual_writes - expected_writes}; "
        f"missing destructive: {expected_writes - actual_writes}"
    )


def test_read_only_routing_tools_are_safe_reads(surface: dict[str, object]) -> None:
    """The tools a client's safety layer was blocking — the read-only preflight/routing + discovery
    helpers — must present as unambiguous safe reads (this is the fix's direct target)."""
    safe_reads = [
        "pa_prompt_route",
        "pa_prompt_route_explain",
        "pa_tool_family_get",
        "pa_workflow_recipe_get",
        "pa_tool_surface_freshness_check",
        "pa_tool_surface_runtime_attestation",
        "hb_assistant_catalog",
        "hb_assistant_tool_help",
    ]
    for name in safe_reads:
        assert name in surface, f"{name} not registered"
        ann = surface[name].annotations
        assert ann is not None and ann.readOnlyHint is True and ann.destructiveHint is False, (name, ann)


def test_gateway_proxy_marked_write(surface: dict[str, object]) -> None:
    """The gateway proxy (``hb_assistant_tool_query``) can route to a canonical write, so it is annotated
    write-capable even though the broker's own ``_access_mode`` calls it read. Its catalog/help siblings
    stay read (pure discovery)."""
    assert surface["hb_assistant_tool_query"].annotations.destructiveHint is True
    assert surface["hb_assistant_catalog"].annotations.readOnlyHint is True
    assert surface["hb_assistant_tool_help"].annotations.readOnlyHint is True


def test_invocation_meta_present(surface: dict[str, object]) -> None:
    """Every tool carries the openai/toolInvocation status hints (mirrors the Obsidian MCP pattern)."""
    for name, tool in surface.items():
        meta = tool.meta or {}
        assert meta.get("openai/toolInvocation/invoking") == f"Running {name}", name
        assert meta.get("openai/toolInvocation/invoked") == f"Completed {name}", name
