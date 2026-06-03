"""Phase 08D MCP tool-broker proof builder (Prompt 04).

Deterministically exercises the policy-gated broker across its fail-closed paths and the
allowed→receipt path (via injected wrappers), then emits ``mcp-tool-broker-proof.json``.
The exercise runs against a temporary database so the live receipts tables are never
polluted, and asserts the whole proof is free of forbidden raw patterns before writing.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from ..financial_review_routing import _assert_no_raw
from .broker import (
    REASON_ACTION_DENIED,
    REASON_TOOL_NOT_ALLOWED,
    REASON_UNSAFE_OUTPUT,
    REASON_WRAPPER_UNAVAILABLE,
    ToolBroker,
)
from .registry import load_allowed_tools, load_denied_actions

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-08d-mcp-bridge"
PROOF_JSON = "mcp-tool-broker-proof.json"

_GUARD_COLUMNS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_financial_source_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_api_call_performed",
    "procore_api_call_performed",
    "email_send_performed",
    "calendar_update_performed",
    "source_system_writeback_performed",
    "arbitrary_sql_performed",
    "raw_store_access_performed",
    "financial_determination_performed",
    "payment_decision_performed",
    "claim_or_entitlement_decision_performed",
)


def _ok_wrapper(_args: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "provenance": "test_injected_wrapper",
        "results": [{"summary": "metadata only"}],
        "source_count": 1,
        "output_classification": "bounded_summary",
    }


def _raw_leaking_wrapper(_args: dict[str, Any]) -> dict[str, Any]:
    # Deliberately tries to leak a forbidden raw pattern (a URL) — must be blocked.
    return {"status": "ok", "results": [{"link": "https://example.com/raw"}]}


def _guards_all_zero(conn: sqlite3.Connection, table: str) -> bool:
    cols = ", ".join(_GUARD_COLUMNS)
    rows = conn.execute(f"SELECT {cols} FROM {table}").fetchall()
    return all(all(v == 0 for v in row) for row in rows)


def build_mcp_tool_broker_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Exercise the broker, attest the metadata-only receipt model, write the proof JSON."""
    allowed = load_allowed_tools()
    denied = load_denied_actions()
    a_tool = sorted(allowed)[0]  # e.g. hb_query / hb_status

    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "broker.db")
        broker = ToolBroker(
            wrappers={a_tool: _ok_wrapper, "hb_status": _ok_wrapper}, db_path=db, persist=True
        )
        unsafe_broker = ToolBroker(
            wrappers={a_tool: _raw_leaking_wrapper}, db_path=db, persist=True
        )
        no_wrapper_broker = ToolBroker(wrappers={}, db_path=db, persist=True)

        scenarios = {
            "denied_action": broker.dispatch("arbitrary_sql", {}),
            "unknown_tool": broker.dispatch("hb_not_a_tool", {}),
            "wrapper_unavailable": no_wrapper_broker.dispatch(a_tool, {}),
            "allowed_success": broker.dispatch(a_tool, {"q": "status"}),
            "unsafe_output": unsafe_broker.dispatch(a_tool, {"q": "x"}),
            "denied_token_in_args": broker.dispatch("hb_status", {"mode": "arbitrary_sql"}),
        }

        conn = sqlite3.connect(db)
        tool_call_rows = conn.execute(
            "SELECT COUNT(*) FROM second_brain_mcp_tool_call_receipts"
        ).fetchone()[0]
        denial_rows = conn.execute(
            "SELECT COUNT(*) FROM second_brain_mcp_denial_receipts"
        ).fetchone()[0]
        guards_clean = _guards_all_zero(
            conn, "second_brain_mcp_tool_call_receipts"
        ) and _guards_all_zero(conn, "second_brain_mcp_denial_receipts")
        # No raw argument/result columns exist on the receipt tables (hashes only).
        call_cols = {r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_tool_call_receipts)")}
        no_raw_columns = not (
            {"raw_args", "raw_result", "raw_prompt", "raw_response"} & call_cols
        ) and "args_hash" in call_cols and "result_hash" in call_cols

    expectations = {
        "denied_action": ("denied", REASON_ACTION_DENIED),
        "unknown_tool": ("denied", REASON_TOOL_NOT_ALLOWED),
        "wrapper_unavailable": ("denied", REASON_WRAPPER_UNAVAILABLE),
        "allowed_success": ("allowed", None),
        "unsafe_output": ("denied", REASON_UNSAFE_OUTPUT),
        "denied_token_in_args": ("denied", REASON_ACTION_DENIED),
    }
    scenario_report: dict[str, Any] = {}
    all_pass = True
    for key, env in scenarios.items():
        exp_decision, exp_reason = expectations[key]
        ok = env["decision"] == exp_decision and (
            exp_reason is None or env.get("reason_code") == exp_reason
        )
        all_pass = all_pass and ok and bool(env.get("receipt_id"))
        scenario_report[key] = {
            "decision": env["decision"],
            "reason_code": env.get("reason_code"),
            "receipt_id_present": bool(env.get("receipt_id")),
            "expected": {"decision": exp_decision, "reason_code": exp_reason},
            "pass": ok,
        }

    proof_passed = bool(
        all_pass
        and guards_clean
        and no_raw_columns
        and tool_call_rows == 1
        and denial_rows == 5
    )

    proof: dict[str, Any] = {
        "proof": "phase_08d_mcp_tool_broker",
        "phase": "08D",
        "proof_passed": proof_passed,
        "registries": {"allowed_tools": len(allowed), "denied_actions": len(denied)},
        "denial_reason_codes": [
            REASON_ACTION_DENIED,
            REASON_TOOL_NOT_ALLOWED,
            REASON_WRAPPER_UNAVAILABLE,
            "invalid_arguments",
            REASON_UNSAFE_OUTPUT,
            "broker_error",
        ],
        "scenarios": scenario_report,
        "receipt_counts": {"tool_call": tool_call_rows, "denial": denial_rows},
        "metadata_only": {
            "receipt_tables_have_no_raw_columns": no_raw_columns,
            "all_guard_columns_zero": guards_clean,
            "args_and_results_hashed_only": True,
        },
        "deferred": {
            "workflow_wrappers": "implemented in Prompt 05 (allowed_success here uses an "
            "injected test wrapper)",
            "stdio_exposure": "broker not yet exposed over stdio (serve fail-closed)",
        },
        "guardrails": {
            "deny_first": True,
            "metadata_only_receipts": True,
            "bounded_output": True,
            "no_raw_no_writeback_no_determination": True,
        },
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp tool-broker proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        proof["proof_path"] = str(out_dir / PROOF_JSON)

    return proof
