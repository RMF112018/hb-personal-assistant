"""Phase 09 Addendum — MCP daily-brief handoff tool (hb_daily_brief_packet) tests."""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.daily_brief import packet as pkt
from hb_assistant.construction.second_brain.daily_brief.packet import (
    load_daily_brief_packet_v2_contract,
)
from hb_assistant.construction.second_brain.mcp import (
    build_default_broker,
    build_mcp_daily_brief_handoff_proof,
    build_no_mcp_writeback_proof,
    build_no_raw_mcp_access_proof,
)
from hb_assistant.construction.second_brain.mcp.proof import (
    _FORBIDDEN_RESULT_FIELDS,
    _collect_keys,
)
from hb_assistant.construction.second_brain.mcp.registry import load_allowed_tools

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|https?://|access_token|refresh_token|client_secret"
)

_TOOL = "hb_daily_brief_packet"


def _seeded_broker(td: str):
    db = str(Path(td) / "seeded.sqlite3")
    pkt._seed_proof_db(db)
    return build_default_broker(db_path=db, persist=True), db


def test_tool_is_registered() -> None:
    allowed = load_allowed_tools()
    assert _TOOL in allowed
    assert allowed[_TOOL]["wrapper"] == "mcp_daily_brief_packet_wrapper"


def test_tool_output_matches_packet_contract() -> None:
    contract = load_daily_brief_packet_v2_contract()
    with tempfile.TemporaryDirectory() as td:
        broker, _db = _seeded_broker(td)
        env = broker.dispatch(_TOOL, {"date": "2026-06-02", "project_scope": "P1"})
        assert env["decision"] == "allowed"
        packet = env["result"]["results"][0]
        render = packet["render_payload"]
        governance = packet["governance_metadata"]
        assert governance["packet_version"] == "DailyBriefHandoffPacketV2"
        for section in contract["render_payload_sections"]:
            assert section in render, section
        for field in contract["governance_metadata_fields"]:
            assert field in governance, field
        # No governance key leaks into the render body.
        for forbidden in contract["forbidden_in_render_payload"]:
            assert forbidden not in render, forbidden


def test_tool_is_read_only_no_writeback() -> None:
    with tempfile.TemporaryDirectory() as td:
        broker, db = _seeded_broker(td)
        env = broker.dispatch(_TOOL, {"date": "2026-06-02", "project_scope": "P1"})
        assert env["decision"] == "allowed"
        assert env["policy_posture"]["no_writeback"] is True
        conn = sqlite3.connect(db)
        try:
            runs = conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0]
        finally:
            conn.close()
        assert runs == 0


def test_tool_emits_no_raw_shaped_fields() -> None:
    with tempfile.TemporaryDirectory() as td:
        broker, _db = _seeded_broker(td)
        env = broker.dispatch(_TOOL, {"date": "2026-06-02", "project_scope": "P1"})
        blob = json.dumps(env, default=str)
        assert not _SECRET_OR_URL.search(blob)
        # Forbidden raw FIELD NAMES must not appear as keys.
        assert not (set(_FORBIDDEN_RESULT_FIELDS) & _collect_keys(env))
        # Source refs (under governance_metadata) are hashed only.
        governance = env["result"]["results"][0]["governance_metadata"]
        for ref in governance["source_refs"]:
            assert "source_ref" not in ref
            assert ref["source_ref_hash"]


def test_tool_does_not_expose_direct_db_vector_graph_procore() -> None:
    with tempfile.TemporaryDirectory() as td:
        broker, _db = _seeded_broker(td)
        # Explicit denied actions stay denied.
        for action in (
            "arbitrary_sql",
            "raw_sqlite_query",
            "graph_api_call",
            "procore_api_call",
            "source_system_writeback",
            "raw_file_read",
        ):
            assert broker.dispatch(action, {})["decision"] == "denied", action
        # Denied token riding in args is denied.
        assert broker.dispatch(_TOOL, {"q": "graph_api_call"})["decision"] == "denied"


def test_tool_cannot_write_or_accept_memory() -> None:
    with tempfile.TemporaryDirectory() as td:
        broker, _db = _seeded_broker(td)
        # Memory mutation / vector search / brief apply are not allowed tools → denied by default.
        for action in ("memory_accept", "memory_write", "vector_index_search", "daily_brief_apply"):
            assert broker.dispatch(action, {})["decision"] == "denied", action


def test_missing_inputs_fail_safe() -> None:
    with tempfile.TemporaryDirectory() as td:
        broker, _db = _seeded_broker(td)
        env = broker.dispatch(_TOOL, {})  # no date / no project_scope → defaults
        assert env["decision"] == "allowed"
        assert not _SECRET_OR_URL.search(json.dumps(env, default=str))


def test_include_rendering_instructions_toggle() -> None:
    with tempfile.TemporaryDirectory() as td:
        broker, _db = _seeded_broker(td)
        on = broker.dispatch(_TOOL, {"project_scope": "P1", "include_rendering_instructions": True})
        off = broker.dispatch(
            _TOOL, {"project_scope": "P1", "include_rendering_instructions": False}
        )
        on_gov = on["result"]["results"][0]["governance_metadata"]
        off_gov = off["result"]["results"][0]["governance_metadata"]
        assert "rendering_instructions" in on_gov
        assert "rendering_instructions" not in off_gov
        # Guardrails (under governance_metadata) are always present.
        assert off_gov["guardrails"]["no_writeback"] is True


def test_mcp_no_raw_and_no_writeback_proofs_remain_green() -> None:
    assert build_no_raw_mcp_access_proof(write_evidence=False)["proof_passed"] is True
    assert build_no_mcp_writeback_proof(write_evidence=False)["proof_passed"] is True


def test_handoff_proof_passes_and_writes_artifacts(tmp_path) -> None:
    proof = build_mcp_daily_brief_handoff_proof(evidence_dir=str(tmp_path), write_evidence=True)
    assert proof["proof_passed"] is True
    for key in (
        "tool_registered",
        "dispatch_allowed",
        "output_matches_contract",
        "items_match_contract",
        "packet_version_ok",
        "no_raw_emitted",
        "no_forbidden_result_fields",
        "read_only_no_writeback",
        "missing_inputs_fail_safe",
        "deny_first_preserved",
        "mcp_no_raw_proof_passed",
        "mcp_no_writeback_proof_passed",
    ):
        assert proof[key] is True, f"{key} not True"
    pj = tmp_path / "mcp-daily-brief-handoff-proof.json"
    pm = tmp_path / "mcp-daily-brief-handoff-proof.md"
    assert pj.exists() and pm.exists()
    assert not _SECRET_OR_URL.search(pj.read_text())
