"""Phase 08D Prompt 05 — the nine MCP allowed workflow wrappers.

Proves each wrapper runs offline on an empty temp DB, returns the bounded contract shape
without raising, and never surfaces raw content; that dispatch through the real broker
yields nine allowed, metadata-only receipts; and that hb_open_daily_brief never opens and
hb_memory_feedback records only a local feedback-log row.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.mcp import (
    build_default_broker,
    build_mcp_allowed_tools_proof,
    build_wrapper_registry,
)
from hb_assistant.construction.second_brain.mcp.proof import _FORBIDDEN_RESULT_FIELDS
from hb_assistant.construction.second_brain.mcp.registry import load_allowed_tools
from hb_assistant.construction.second_brain.mcp.wrappers import (
    mcp_memory_feedback_wrapper,
    mcp_open_daily_brief_wrapper,
    mcp_status_wrapper,
)

_ENVELOPE_KEYS = {"status", "provenance", "results", "source_count", "output_classification"}


def _tmpdb(td: str) -> str:
    return str(Path(td) / "w.db")


def test_registry_has_nine_wrappers_for_every_allowed_tool() -> None:
    registry = build_wrapper_registry()
    allowed = load_allowed_tools()
    assert set(registry) == set(allowed)
    assert len(registry) == 9


def test_every_wrapper_returns_bounded_shape_offline() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _tmpdb(td)
        registry = build_wrapper_registry(db_path=db)
        sample = {
            "hb_query": {"question": "what is the status?"},
            "hb_memory_feedback": {"target_id": "c1", "feedback_class": "accept"},
        }
        for name, wrapper in registry.items():
            out = wrapper(sample.get(name, {}))
            assert set(out) >= _ENVELOPE_KEYS, f"{name} missing envelope keys"
            assert isinstance(out["results"], list)
            assert len(out["results"]) <= 50
            blob = json.dumps(out, default=str)
            for forbidden in _FORBIDDEN_RESULT_FIELDS:
                assert forbidden not in blob, f"{name} leaked {forbidden}"


def test_status_wrapper_reports_runtime_posture() -> None:
    out = mcp_status_wrapper({})
    assert out["status"] in ("ok", "degraded")
    row = out["results"][0]
    assert "runtime_mode" in row or "reason_code" in row


def test_open_daily_brief_never_opens() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = mcp_open_daily_brief_wrapper({}, db_path=_tmpdb(td))
        row = out["results"][0]
        # status-only: never applied an open
        assert row.get("opened") in (False, None)


def test_memory_feedback_requires_target_and_writes_local_row() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _tmpdb(td)
        # missing target -> degraded, no write
        blocked = mcp_memory_feedback_wrapper({}, db_path=db)
        assert blocked["status"] == "degraded"
        # with target -> records a local feedback row
        ok = mcp_memory_feedback_wrapper(
            {"target_id": "cand-1", "feedback_class": "accept"}, db_path=db
        )
        assert ok["status"] == "ok"
        assert ok["results"][0]["recorded"] is True
        conn = sqlite3.connect(db)
        n = conn.execute("SELECT COUNT(*) FROM second_brain_operator_feedback").fetchone()[0]
        assert n == 1


def test_broker_dispatch_allows_all_nine_with_metadata_receipts() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _tmpdb(td)
        broker = build_default_broker(db_path=db, persist=True)
        sample = {
            "hb_query": {"question": "status?"},
            "hb_memory_feedback": {"target_id": "c1", "feedback_class": "accept"},
        }
        for name in load_allowed_tools():
            env = broker.dispatch(name, sample.get(name, {}))
            assert env["decision"] == "allowed", f"{name} was not allowed: {env.get('reason_code')}"
            assert env["receipt_id"]
            assert env["policy_posture"]["no_writeback"] is True
        conn = sqlite3.connect(db)
        receipts = conn.execute(
            "SELECT COUNT(*) FROM second_brain_mcp_tool_call_receipts"
        ).fetchone()[0]
        assert receipts == 9


def test_allowed_tools_contract_proof_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_mcp_allowed_tools_proof(evidence_dir=td, write_evidence=True)
        assert proof["proof_passed"] is True
        assert proof["tool_count"] == 9
        assert proof["tool_call_receipts"] == 9
        assert proof["metadata_only"]["all_guard_columns_zero"] is True
        assert proof["metadata_only"]["no_forbidden_result_fields"] is True
        assert (Path(td) / "mcp-tool-contract-proof.json").exists()
