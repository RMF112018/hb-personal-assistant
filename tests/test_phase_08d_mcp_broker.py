"""Phase 08D Prompt 04 — policy-gated MCP tool broker.

Proves deny-first dispatch, fail-closed reason codes, bounded + no-raw output validation,
and metadata-only receipts (hashes/counts only; all guard columns 0). The nine workflow
wrappers land in Prompt 05; the allowed→receipt path is exercised here with an injected
test wrapper.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from hb_assistant.construction.second_brain.mcp.broker import (
    MAX_RESULTS,
    REASON_ACTION_DENIED,
    REASON_INVALID_ARGUMENTS,
    REASON_TOOL_NOT_ALLOWED,
    REASON_UNSAFE_OUTPUT,
    REASON_WRAPPER_UNAVAILABLE,
    ToolBroker,
)
from hb_assistant.construction.second_brain.mcp.proof import build_mcp_tool_broker_proof
from hb_assistant.construction.second_brain.mcp.registry import (
    load_allowed_tools,
    load_denied_actions,
)


def _ok_wrapper(_args: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "provenance": "test",
        "results": [{"summary": "metadata only"}],
        "source_count": 1,
        "output_classification": "bounded_summary",
    }


def _broker(db: str, wrappers: dict[str, Any] | None = None) -> ToolBroker:
    return ToolBroker(wrappers=wrappers or {}, db_path=db, persist=True)


def test_registries_load_nine_allowed_and_denied_actions() -> None:
    allowed = load_allowed_tools()
    denied = load_denied_actions()
    assert len(allowed) == 9
    assert "hb_status" in allowed and allowed["hb_status"]["wrapper"] == "mcp_status_wrapper"
    assert "arbitrary_sql" in denied and "graph_api_call" in denied
    assert len(denied) >= 25


def test_denied_action_is_denied_with_denial_receipt() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        env = _broker(db).dispatch("arbitrary_sql", {})
        assert env["decision"] == "denied"
        assert env["reason_code"] == REASON_ACTION_DENIED
        assert env["receipt_id"]
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT requested_action, decision, denial_reason_code FROM second_brain_mcp_denial_receipts"
        ).fetchone()
        assert row == ("arbitrary_sql", "denied", REASON_ACTION_DENIED)


def test_unknown_tool_is_denied() -> None:
    with tempfile.TemporaryDirectory() as td:
        env = _broker(str(Path(td) / "b.db")).dispatch("hb_not_real", {})
        assert env["decision"] == "denied"
        assert env["reason_code"] == REASON_TOOL_NOT_ALLOWED


def test_allowed_tool_without_wrapper_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        env = _broker(str(Path(td) / "b.db")).dispatch("hb_query", {})
        assert env["decision"] == "denied"
        assert env["reason_code"] == REASON_WRAPPER_UNAVAILABLE


def test_denied_token_in_arguments_is_denied() -> None:
    with tempfile.TemporaryDirectory() as td:
        env = _broker(str(Path(td) / "b.db"), {"hb_status": _ok_wrapper}).dispatch(
            "hb_status", {"mode": "graph_api_call"}
        )
        assert env["decision"] == "denied"
        assert env["reason_code"] == REASON_ACTION_DENIED


def test_invalid_arguments_are_denied() -> None:
    with tempfile.TemporaryDirectory() as td:
        broker = _broker(str(Path(td) / "b.db"), {"hb_status": _ok_wrapper})
        oversize = broker.dispatch("hb_status", {"blob": "x" * (17 * 1024)})
        assert oversize["decision"] == "denied"
        assert oversize["reason_code"] == REASON_INVALID_ARGUMENTS


def test_allowed_tool_with_wrapper_succeeds_and_writes_metadata_receipt() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        env = _broker(db, {"hb_status": _ok_wrapper}).dispatch("hb_status", {"q": "x"})
        assert env["decision"] == "allowed"
        assert env["denied"] is False
        assert env["result_count"] == 1
        assert env["receipt_id"]
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT tool_name, decision, workflow_wrapper, args_hash, result_hash, "
            "result_count, raw_prompt_persisted, external_writeback_performed "
            "FROM second_brain_mcp_tool_call_receipts"
        ).fetchone()
        tool, decision, wrapper, args_hash, result_hash, rcount, raw_prompt, ext_wb = row
        assert (tool, decision, wrapper) == ("hb_status", "allowed", "mcp_status_wrapper")
        assert args_hash and result_hash and len(args_hash) == 64
        assert rcount == 1
        assert (raw_prompt, ext_wb) == (0, 0)
        # receipt table has no raw arg/result columns
        cols = {r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_tool_call_receipts)")}
        assert not ({"raw_args", "raw_result"} & cols)


def test_unsafe_wrapper_output_is_blocked() -> None:
    def leaky(_args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "results": [{"url": "https://example.com/secret"}]}

    with tempfile.TemporaryDirectory() as td:
        env = _broker(str(Path(td) / "b.db"), {"hb_status": leaky}).dispatch("hb_status", {})
        assert env["decision"] == "denied"
        assert env["reason_code"] == REASON_UNSAFE_OUTPUT
        # the raw url never appears in the safe envelope
        assert "example.com" not in str(env)


def test_output_is_bounded_to_max_results() -> None:
    def many(_args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "results": [{"i": i} for i in range(MAX_RESULTS + 25)]}

    with tempfile.TemporaryDirectory() as td:
        env = _broker(str(Path(td) / "b.db"), {"hb_status": many}).dispatch("hb_status", {})
        assert env["decision"] == "allowed"
        assert env["result_count"] == MAX_RESULTS
        assert len(env["result"]["results"]) == MAX_RESULTS


def test_broker_proof_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_mcp_tool_broker_proof(evidence_dir=td, write_evidence=True)
        assert proof["proof_passed"] is True
        assert proof["registries"] == {"allowed_tools": 9, "denied_actions": len(load_denied_actions())}
        assert proof["metadata_only"]["all_guard_columns_zero"] is True
        assert (Path(td) / "mcp-tool-broker-proof.json").exists()
