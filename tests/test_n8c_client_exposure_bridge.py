"""N8C-22 — connected-client assistant tool exposure bridge.

Proves *client-level* exposure (not merely internal broker registration): all 87 canonical assistant
tools land in the live FastMCP client manifest, the 3 ``hb_assistant_*`` bridge helpers exist and stay
separate from the canonical 87, the fallback catalog/help/gateway behave and fail closed, and no new
write/raw surface leaks. Built against a REAL FastMCP surface — the same object whose ``tools/list`` a
connected client calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
    ALL_ASSISTANT_TOOLS,
    ASSISTANT_TOOL_GROUPS,
    DENIED_TOOL_NAMES,
    GATEWAY_ALLOWLIST,
    NasMcpBroker,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.exposure_audit import build_exposure_audit
from hb_assistant.nas_mcp.profile import AI_OUTPUTS_WRITE_TOOL
from hb_assistant.nas_mcp.tool_registration import (
    CLIENT_BRIDGE_HELPER_TOOLS,
    register_nas_mcp_tools,
)
from hb_assistant.store.migrator import SQLiteMigrator

# Write/finality verbs that must never appear in a bridge helper name (the helpers escape the
# ``assistant_``-prefixed finality guard, so we assert their cleanliness directly).
_FORBIDDEN_VERB_SUBSTRINGS = (
    "dispatch", "execute", "apply", "write", "create", "delete", "upsert", "persist",
    "answer", "generate", "evaluate", "repair", "send", "schedule", "scan", "reindex", "rebuild",
)

_REPRESENTATIVE_TOOLS = (
    "assistant_search_sources",
    "assistant_source_file_search",
    "assistant_source_file_read",
    "assistant_list_context_packs",
    "assistant_get_context_pack",
    "assistant_list_memory_nodes",
    "assistant_list_decisions",
    "assistant_list_research_packets",
    "assistant_get_research_packet",
    "assistant_list_drafts",
    "assistant_route_workflow",
    "assistant_list_review_items",
    "assistant_list_feedback",
    "assistant_list_action_stages",
    "assistant_list_quality",
    "assistant_get_quality_findings",
)


def _synthetic_value(spec: dict) -> object:
    kind = spec.get("type")
    if kind in ("integer", "number"):
        return 1
    if kind == "boolean":
        return False
    if kind == "array":
        return []
    if kind == "object":
        return {}
    return "n8c22-nonexistent-id"


def _synthetic_args(schema: dict) -> dict:
    props = schema.get("properties") or {}
    return {name: _synthetic_value(props.get(name, {})) for name in (schema.get("required") or [])}


@pytest.fixture()
def surface(tmp_path: Path, monkeypatch):
    """A REAL FastMCP surface + migrated test DB. Returns broker + {name: live Tool}.

    This file verifies FULL canonical parity — that every one of the 87 canonical assistant tools is
    exposable and consistent. The ``source_structure`` group is default-OFF (opt-in), so it must be
    enabled here to see the complete surface; its default-off (installed-but-disabled) behavior is
    covered separately in ``test_source_structure_mcp_tools.py``.
    """
    from mcp.server.fastmcp import FastMCP

    monkeypatch.setenv("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = NasMcpConfig(
        db_path=Path(db),
        audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(
            vault_root=vault, backup_dir=tmp_path / "bk", support_dir=tmp_path / "sup"
        ),
    )
    mcp = FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)
    broker = NasMcpBroker(cfg)
    register_nas_mcp_tools(mcp, broker)
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    return {"broker": broker, "tools": tools, "names": set(tools)}


# ---------- exposure parity ----------

def test_all_85_canonical_tools_in_client_manifest(surface) -> None:
    names = surface["names"]
    assert set(ALL_ASSISTANT_TOOLS) <= names, set(ALL_ASSISTANT_TOOLS) - names
    from hb_assistant.nas_mcp.client_output_tools import ASSISTANT_OUTPUT_ALIASES
    assert set(ALL_ASSISTANT_TOOLS) <= names
    # Canonical 87 + assistant_output_* aliases (write gate may omit 3 write aliases)
    assert len([n for n in names if n.startswith("assistant_")]) >= 87
    assert len([n for n in names if n.startswith("assistant_")]) <= 87 + len(ASSISTANT_OUTPUT_ALIASES)


def test_three_bridge_helpers_registered_and_separate(surface) -> None:
    names = surface["names"]
    assert set(CLIENT_BRIDGE_HELPER_TOOLS) <= names
    assert len(CLIENT_BRIDGE_HELPER_TOOLS) == 3
    # Helpers are NOT part of the canonical 87 and are NOT assistant_-prefixed.
    for helper in CLIENT_BRIDGE_HELPER_TOOLS:
        assert helper not in ALL_ASSISTANT_TOOLS
        assert not helper.startswith("assistant_")
        assert not any(v in helper for v in _FORBIDDEN_VERB_SUBSTRINGS), helper


def test_no_denied_tool_is_client_exposed(surface) -> None:
    assert DENIED_TOOL_NAMES.isdisjoint(surface["names"])


def test_exposure_audit_reports_no_code_level_gap(monkeypatch) -> None:
    # Enable the default-off group so the audit sees the full canonical surface exposed (85).
    monkeypatch.setenv("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", "1")
    audit = build_exposure_audit()
    s = audit["summary"]
    assert s["broker_registered"] == 87
    assert s["installed_total"] == 87
    assert s["expected_exposed"] == 87
    assert s["status_advertised"] == 87
    assert s["client_manifest_exposed"] == 87
    assert s["callable_smoke_tested"] == 87
    assert s["missing_from_client_manifest"] == 0
    assert s["not_callable"] == 0
    assert "NO CODE-LEVEL GAP" in audit["conclusion"]


def test_exposure_audit_default_off_group_is_not_a_gap(monkeypatch) -> None:
    # With the group default-off, its 7 tools are installed-but-disabled — NOT a code-level gap.
    monkeypatch.setenv("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", "0")
    audit = build_exposure_audit()
    s = audit["summary"]
    assert s["installed_total"] == 87
    assert s["expected_exposed"] == 80
    assert s["client_manifest_exposed"] == 80
    assert s["missing_from_client_manifest"] == 0
    assert len(s["installed_but_disabled"]) == 7
    assert "NO CODE-LEVEL GAP" in audit["conclusion"]


# ---------- direct wrapper reach ----------

def test_direct_wrappers_reach_handler_path(surface) -> None:
    tools = surface["tools"]
    for name in _REPRESENTATIVE_TOOLS:
        tool = tools[name]
        args = _synthetic_args(getattr(tool, "parameters", None) or {})
        try:
            out = tool.fn(**args)
            assert isinstance(out, dict), name
        except ValueError:
            # Reached the audited handler and fail-closed on a synthetic id — still proves reach.
            pass


# ---------- catalog ----------

def test_catalog_lists_all_groups_and_tools(surface) -> None:
    cat = surface["tools"]["hb_assistant_catalog"].fn()
    assert len(cat["groups"]) == 14
    assert len(cat["tools"]) == 87
    assert cat["canonical_assistant_tool_count"] == 87
    assert cat["client_bridge_helper_tools"] == list(CLIENT_BRIDGE_HELPER_TOOLS)
    assert cat["exposure"]["assistant_client_exposed_tool_count"] == 87
    # No secrets / raw payloads leaked — every tool entry is a bounded read (no write class). The
    # canonical assistant suite classifies uniformly as ``bounded_read`` via classify_tool (the old
    # blanket ``read_only_advisory`` label was retired when write surfaces joined the gateway).
    for entry in cat["tools"]:
        assert entry["safety_class"] == "bounded_read"
        assert set(entry) >= {"tool_name", "group", "required_args", "optional_args"}


def test_catalog_group_filter_and_rejects_unknown(surface) -> None:
    nav = surface["tools"]["hb_assistant_catalog"].fn(group="nav")
    assert len(nav["groups"]) == 1
    assert len(nav["tools"]) == len(ASSISTANT_TOOL_GROUPS["nav"]) == 12
    with pytest.raises(ValueError, match="unknown_assistant_group"):
        surface["tools"]["hb_assistant_catalog"].fn(group="bogus")


# ---------- help ----------

def test_help_returns_schema_for_known_tool(surface) -> None:
    meta = surface["tools"]["hb_assistant_tool_help"].fn("assistant_source_file_search")
    assert meta["tool_name"] == "assistant_source_file_search"
    assert "query" in meta["required_args"]
    assert meta["input_schema"].get("properties")
    assert meta["gateway"] == "hb_assistant_tool_query"


# N8C-24: the gateway allowlist was deliberately expanded to reach the write surfaces, so
# ai_outputs_card_upsert is now gateway-reachable. Denied/root-db/legacy/unknown stay rejected.
@pytest.mark.parametrize("bad", ["hb_db_select", "raw_sql", "shell", "hb_output_write_file", "bogus_tool"])
def test_help_rejects_unknown_denied_and_non_assistant(surface, bad) -> None:
    with pytest.raises(ValueError):
        surface["tools"]["hb_assistant_tool_help"].fn(bad)


# ---------- gateway ----------

def test_gateway_calls_allowlisted_assistant_tool(surface) -> None:
    receipt = surface["tools"]["hb_assistant_tool_query"].fn("assistant_list_context_packs", {})
    assert receipt["ok"] is True
    assert receipt["tool"] == "assistant_list_context_packs"
    assert receipt.get("request_id")


@pytest.mark.parametrize(
    "tool_name,args",
    [
        ("raw_sql", {}),
        ("sql", {}),
        ("shell", {}),
        ("exec", {}),
        ("read_file_absolute", {}),
        ("hb_output_delete", {}),
        ("hb_db_select", {"table_key": "x", "columns": ["a"]}),
        ("hb_output_write_file", {}),  # legacy scratch writer stays gateway-rejected
        ("os.system", {}),
        ("assistant_unknown_tool", {}),
        ("hb_root_read_file", {"root_key": "home", "relative_path": "/etc/passwd"}),
    ],
)
def test_gateway_rejects_denied_write_and_non_allowlisted(surface, tool_name, args) -> None:
    # N8C-24: ai_outputs_card_upsert and the pa_* write surfaces are now gateway-reachable (operator-
    # authorized); denied tools, root/db tools, legacy hb_output_*, and non-allowlisted names stay rejected.
    with pytest.raises(ValueError):
        surface["tools"]["hb_assistant_tool_query"].fn(tool_name, args)


def test_gateway_rejects_bad_args_and_unbounded_limits(surface) -> None:
    q = surface["tools"]["hb_assistant_tool_query"].fn
    with pytest.raises(ValueError, match="arguments_must_be_object"):
        q("assistant_search_sources", ["not", "a", "dict"])
    with pytest.raises(ValueError, match="limit_exceeds_max"):
        q("assistant_search_sources", {"query": "x", "limit": 100000})
    with pytest.raises(ValueError, match="limit_exceeds_max"):
        q("assistant_source_file_read", {"source_ref": "x", "max_chars": 10_000_000})


def test_gateway_preserves_group_kill_switch(surface, monkeypatch) -> None:
    # The quality tool is registered (built with the gate ON), but a kill switch flipped at call time
    # must still fail the dispatch closed through the gateway (broker re-checks the gate).
    monkeypatch.setenv("HB_MCP_ASSISTANT_QUALITY", "0")
    receipt = surface["tools"]["hb_assistant_tool_query"].fn("assistant_list_quality", {})
    assert receipt["ok"] is False
    assert "quality_disabled" in str(receipt.get("error", ""))


# ---------- safety regression ----------

def test_ai_outputs_remains_only_pre_existing_write_and_stays_gate_enforced(surface, monkeypatch) -> None:
    # N8C-24 (operator-authorized): ai_outputs_card_upsert is now REACHABLE via the gateway, but it stays the
    # only PRE-EXISTING write, stays out of the canonical assistant surface, and every gateway-routed call
    # still passes the full broker write-gate chain. Proof: with the write gate flipped OFF, the gateway call
    # fails closed at dispatch (routed, not silently allowed) rather than raising not_allowlisted.
    names = surface["names"]
    assert AI_OUTPUTS_WRITE_TOOL in names
    assert AI_OUTPUTS_WRITE_TOOL not in ALL_ASSISTANT_TOOLS  # not part of the canonical 87
    assert AI_OUTPUTS_WRITE_TOOL in GATEWAY_ALLOWLIST  # now gateway-reachable
    monkeypatch.setenv("HB_MCP_ALLOW_AI_OUTPUTS_WRITE", "0")
    receipt = surface["tools"]["hb_assistant_tool_query"].fn(AI_OUTPUTS_WRITE_TOOL, {"title": "x"})
    assert receipt["ok"] is False
    assert "write_tool_blocked_by_profile" in str(receipt.get("error", ""))


def test_no_new_raw_or_exec_surface_exposed(surface) -> None:
    names = surface["names"]
    for forbidden in ("raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"):
        assert forbidden not in names
    # No client tool name advertises a raw/exec/scan-rebuild capability.
    for banned in ("raw_sql", "reindex", "rebuild", "email_send", "calendar_update"):
        assert not any(banned in n for n in names)


# ---------- status ----------

def test_status_reports_client_exposure_fields(surface) -> None:
    status = surface["broker"].dispatch("hb_mcp_status", {}).get("result", {})
    assert status["assistant_client_exposure_enabled"] is True
    assert status["assistant_client_exposure_mode"] == "direct+gateway"
    assert status["assistant_client_exposed_tool_count"] == 87
    assert status["assistant_client_missing_tool_count"] == 0
    assert len(status["assistant_client_exposure_groups"]) == 14
    assert status["runtime_commit"]


def test_status_missing_count_tracks_kill_switch(surface, monkeypatch) -> None:
    monkeypatch.setenv("HB_MCP_ASSISTANT_QUALITY", "0")
    status = surface["broker"].dispatch("hb_mcp_status", {}).get("result", {})
    # Baseline is the full 87 (surface fixture enables source_structure); quality group (6 tools)
    # disabled -> counted as missing, not exposed.
    assert status["assistant_client_exposed_tool_count"] == 81
    assert status["assistant_client_missing_tool_count"] == 6
    assert "quality" not in status["assistant_client_exposure_groups"]
