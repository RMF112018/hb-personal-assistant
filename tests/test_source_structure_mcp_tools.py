"""Source-structure MCP tools: default-off installed-but-disabled vs gate-on exposed (three states).

State 1 (baseline): the canonical assistant surface is INSTALLED at 85 / 14 groups (structural).
State 2 (gate OFF, default): the 7 tools are NOT registered/invokable to clients — exposed stays 78.
State 3 (gate ON, test harness): the 7 tools register + dispatch — exposed becomes 85.
"""

from __future__ import annotations

import pytest

from hb_assistant.nas_mcp.broker import (
    ALL_ASSISTANT_TOOLS,
    ASSISTANT_SOURCE_STRUCTURE_TOOLS,
    ASSISTANT_TOOL_GROUPS,
)
from hb_assistant.nas_mcp.exposure_audit import _build_surface, build_exposure_audit
from hb_assistant.obsidian_mcp.source_structure_ingest import (
    generate_deterministic_summaries,
    generate_routing_hints,
    ingest_tree_text,
)
from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository
from hb_assistant.store.migrator import SQLiteMigrator

NEW_TOOLS = set(ASSISTANT_SOURCE_STRUCTURE_TOOLS)
TREE = "/Work/NAS - HB\n├── 21-801-01 NORA\n│   └── Submittals\n└── @eaDir\n"

FINALITY_SUBSTRINGS = (
    "extract", "apply", "write", "create", "delete", "persist", "upsert", "build", "send", "scan",
    "reindex", "rebuild", "execute", "schedule", "task", "email", "calendar", "generate", "answer",
    "remind", "accept", "reject", "defer", "dispose", "close", "reopen",
)


def _seed(db: str) -> None:
    SQLiteMigrator(db).apply()
    repo = SourceStructureRepository(db)
    ingest_tree_text(repo, TREE, apply=True)
    generate_deterministic_summaries(repo)
    generate_routing_hints(repo)


@pytest.fixture()
def gate_off(monkeypatch):
    monkeypatch.delenv("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", raising=False)


@pytest.fixture()
def gate_on(monkeypatch):
    monkeypatch.setenv("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", "1")


# --- State 1: structural installation (gate-independent) -------------------------------------
def test_canonical_surface_installed_at_85_and_14_groups():
    assert len(ALL_ASSISTANT_TOOLS) == 85
    assert len(ASSISTANT_TOOL_GROUPS) == 14
    assert set(ALL_ASSISTANT_TOOLS) >= NEW_TOOLS


def test_new_tool_names_carry_no_finality_substring():
    for t in NEW_TOOLS:
        assert not any(s in t for s in FINALITY_SUBSTRINGS), t


# --- State 2: gate OFF — installed but NOT client-exposed -------------------------------------
def test_gate_off_tools_not_registered(gate_off, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    _broker, tools = _build_surface(db)
    assert NEW_TOOLS.isdisjoint(set(tools))
    assert sum(1 for t in tools if t.startswith("assistant_")) == 78


def test_gate_off_dispatch_is_denied(gate_off, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    broker, _tools = _build_surface(db)
    res = broker.dispatch("assistant_source_root_map", {})
    assert res.get("ok") is False
    assert "disabled" in str(res.get("error"))


def test_gate_off_status_reports_disabled(gate_off, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    broker, _tools = _build_surface(db)
    st = broker.dispatch("hb_mcp_status", {}).get("result", {})
    assert st["assistant_source_structure_enabled"] is False
    assert st["assistant_source_structure_tools"] == []


def test_gate_off_audit_reports_no_code_gap(gate_off, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    audit = build_exposure_audit(db)
    s = audit["summary"]
    assert s["installed_total"] == 85
    assert s["expected_exposed"] == 78
    assert s["client_manifest_exposed"] == 78
    assert s["missing_from_client_manifest"] == 0  # default-off group is not a gap
    assert len(s["installed_but_disabled"]) == 7
    assert not audit["conclusion"].startswith("GAP")


# --- State 3: gate ON — registered, dispatchable, exposed 85 ----------------------------------
def test_gate_on_tools_registered_and_exposed_85(gate_on, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    _broker, tools = _build_surface(db)
    assert set(tools) >= NEW_TOOLS
    assert sum(1 for t in tools if t.startswith("assistant_")) == 85


def test_gate_on_dispatch_returns_bounded_rows(gate_on, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    broker, _tools = _build_surface(db)
    res = broker.dispatch("assistant_source_root_map", {"query_family": "construction_project"})
    assert res["ok"] is True
    assert res["result"]["roots"][0]["root_class"] == "construction_work"
    pm = broker.dispatch("assistant_source_project_map", {"project_number": "21-801-01"})
    assert "submittal" in pm["result"]["doc_family_coverage"]


def test_gate_on_dispatch_never_leaks_absolute_paths(gate_on, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    broker, _tools = _build_surface(db)
    res = broker.dispatch("assistant_source_folder_map", {"root_key": "nas-hb", "include_noise": True})
    blob = repr(res["result"])
    assert "/Users/" not in blob and "'rel_path': '/" not in blob


def test_gate_on_denied_tools_still_denied(gate_on, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    broker, _tools = _build_surface(db)
    assert broker.dispatch("raw_sql", {"sql": "select 1"}).get("ok") is False


def test_gate_on_audit_no_gap(gate_on, tmp_path):
    db = str(tmp_path / "pa.db")
    _seed(db)
    audit = build_exposure_audit(db)
    assert audit["summary"]["expected_exposed"] == 85
    assert audit["summary"]["client_manifest_exposed"] == 85
    assert not audit["conclusion"].startswith("GAP")
