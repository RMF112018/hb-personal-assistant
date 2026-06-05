"""Phase 08D Prompt 06 — MCP denied tools and policy enforcement.

Proves deny-first enforcement for every one of the 27 denied actions (organized below by
conceptual class for readability), that each denial writes a metadata-only denial receipt
naming the action, that a denied token riding in an allowed tool's arguments is denied and
named, and that raw requested content embedded in arguments is never persisted.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.mcp import build_mcp_denied_tools_proof
from hb_assistant.construction.second_brain.mcp.broker import REASON_ACTION_DENIED, ToolBroker
from hb_assistant.construction.second_brain.mcp.registry import load_denied_actions

# The 27 denied actions, grouped into conceptual classes (enforcement is the flat registry).
_DENIAL_CLASSES = {
    "arbitrary_sql": ["arbitrary_sql", "raw_sqlite_query"],
    "raw_store": ["raw_file_read", "raw_obsidian_read"],
    "direct_api": ["graph_api_call", "procore_api_call"],
    "source_writeback": ["email_send", "calendar_update", "source_system_writeback"],
    "raw_payload": [
        "raw_email_body_access",
        "raw_document_text_access",
        "raw_calendar_payload_access",
        "raw_procore_payload_access",
        "raw_financial_payload_access",
        "raw_prompt_access",
        "raw_response_access",
    ],
    "url": ["signed_url_access", "download_url_access"],
    "determination": [
        "payment_decision",
        "claim_decision",
        "entitlement_decision",
        "final_financial_determination",
    ],
    "external_delivery": [
        "external_delivery",
        "slack_send",
        "teams_send",
        "sms_send",
        "push_notification_send",
    ],
}
_ALL_DENIED = [a for actions in _DENIAL_CLASSES.values() for a in actions]


def _broker(db: str) -> ToolBroker:
    return ToolBroker(wrappers={}, db_path=db, persist=True)


def test_denial_class_taxonomy_matches_registry() -> None:
    assert set(_ALL_DENIED) == load_denied_actions()
    assert len(_ALL_DENIED) == 27


@pytest.mark.parametrize("action", _ALL_DENIED)
def test_every_denied_action_is_denied_with_metadata_receipt(action: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "d.db")
        env = _broker(db).dispatch(action, {})
        assert env["decision"] == "denied"
        assert env["reason_code"] == REASON_ACTION_DENIED
        assert env["tool"] == action
        assert env["receipt_id"]
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT requested_action, decision, denial_reason_code, request_hash, "
            "external_writeback_performed, raw_prompt_persisted "
            "FROM second_brain_mcp_denial_receipts"
        ).fetchone()
        req, decision, reason, req_hash, ext_wb, raw_prompt = row
        assert (req, decision, reason) == (action, "denied", REASON_ACTION_DENIED)
        assert req_hash and (ext_wb, raw_prompt) == (0, 0)


def test_denied_token_in_args_names_the_specific_action() -> None:
    with tempfile.TemporaryDirectory() as td:
        env = _broker(str(Path(td) / "d.db")).dispatch("hb_status", {"mode": "arbitrary_sql"})
        assert env["decision"] == "denied"
        assert env["reason_code"] == REASON_ACTION_DENIED
        assert env["tool"] == "arbitrary_sql"


def test_raw_requested_content_is_never_persisted() -> None:
    marker = "RAW-SECRET-zzz-do-not-store"
    url = "https://example.com/leak"
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "d.db")
        _broker(db).dispatch("arbitrary_sql", {"sql": marker, "body": url})
        conn = sqlite3.connect(db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_denial_receipts)")]
        # no raw/content columns exist
        assert not ({"raw_requested_content", "raw_args", "raw_sql", "raw_prompt"} & set(cols))
        blob = " ".join(
            str(v)
            for row in conn.execute(
                f"SELECT {', '.join(cols)} FROM second_brain_mcp_denial_receipts"
            )
            for v in row
            if v is not None
        )
        assert marker not in blob
        assert url not in blob


def test_denied_tools_proof_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_mcp_denied_tools_proof(evidence_dir=td, write_evidence=True)
        assert proof["proof_passed"] is True
        assert proof["denied_action_count"] == 27
        assert proof["denial_receipts_written"] == 29  # 27 actions + token + raw-content
        assert proof["metadata_only"]["no_raw_requested_content_echoed"] is True
        assert proof["metadata_only"]["all_guard_columns_zero"] is True
        assert (Path(td) / "mcp-denied-tool-proof.json").exists()
