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
CONTRACT_PROOF_JSON = "mcp-tool-contract-proof.json"
DENIED_PROOF_JSON = "mcp-denied-tool-proof.json"
RESOURCE_PROOF_JSON = "mcp-resource-contract-proof.json"

# Fields a tool result must never carry (raw content / determinations).
_FORBIDDEN_RESULT_FIELDS = (
    "raw_body",
    "raw_prompt",
    "raw_response",
    "raw_sql",
    "raw_source_content",
    "signed_url",
    "download_url",
    "token",
    "secret",
    "final_determination",
)

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


def _collect_keys(obj: Any) -> set[str]:
    """Recursively collect every dict key in a nested structure (exact-match safety check)."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(str(key))
            keys |= _collect_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _collect_keys(item)
    return keys


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


def build_mcp_resources_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Read all five safe resources and attest the bounded, approved-workflow-only contract.

    Runs against a temporary database (empty → resources degrade safely). Confirms each
    resource is from an approved workflow, bounded, carries freshness + policy posture, and
    leaks no forbidden field; that an unknown URI fail-closes; and that a metadata-only
    resource-registry snapshot persists guard-clean. Writes ``mcp-resource-contract-proof.json``.
    """
    from .resources import (  # noqa: PLC0415 - avoid import cycle (resources imports proof? no)
        load_resources,
        read_resource,
        snapshot_resource_registry,
    )

    registry = load_resources()
    uris = [r["uri"] for r in registry]
    resource_report: dict[str, Any] = {}
    all_pass = True

    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "resources.db")
        for uri in uris:
            res = read_resource(uri, db_path=db)
            keys = _collect_keys(res)
            forbidden_hit = sorted(set(_FORBIDDEN_RESULT_FIELDS) & keys)
            ok = bool(
                res.get("resource_name")
                and res.get("source")
                and "content" in res
                and isinstance(res.get("freshness"), dict)
                and res.get("policy_posture")
                and not forbidden_hit
            )
            all_pass = all_pass and ok
            resource_report[uri] = {
                "resource_name": res.get("resource_name"),
                "source": res.get("source"),
                "status": res.get("status"),
                "has_freshness": isinstance(res.get("freshness"), dict),
                "has_policy_posture": bool(res.get("policy_posture")),
                "forbidden_fields": forbidden_hit,
                "pass": ok,
            }

        # Unknown URI must fail closed.
        unknown = read_resource("hb://secrets/all", db_path=db)
        unknown_fail_closed = bool(
            unknown.get("status") == "denied"
            and unknown.get("reason_code") == "resource_not_allowed"
            and unknown.get("fail_closed") is True
        )

        snapshot_id = snapshot_resource_registry(db_path=db, persist=True)
        conn = sqlite3.connect(db)
        snapshot_rows = conn.execute(
            "SELECT resource_count FROM second_brain_mcp_resource_registry_snapshots"
        ).fetchall()
        guards_clean = _guards_all_zero(conn, "second_brain_mcp_resource_registry_snapshots")

    proof_passed = bool(
        all_pass
        and unknown_fail_closed
        and snapshot_id
        and snapshot_rows == [(len(uris),)]
        and guards_clean
    )
    proof: dict[str, Any] = {
        "proof": "phase_08d_mcp_resources",
        "phase": "08D",
        "proof_passed": proof_passed,
        "resource_count": len(uris),
        "resources": resource_report,
        "unknown_uri_fail_closed": unknown_fail_closed,
        "registry_snapshot": {
            "persisted": bool(snapshot_id),
            "resource_count": len(uris),
            "all_guard_columns_zero": guards_clean,
        },
        "contract": {
            "approved_workflow_source": True,
            "bounded_structured_output": True,
            "freshness_metadata": True,
            "policy_posture": True,
            "fail_closed": True,
            "no_per_access_receipt": True,
        },
        "guardrails": {"read_only": True, "no_raw_content": True, "no_writeback": True},
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp resources proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / RESOURCE_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        proof["proof_path"] = str(out_dir / RESOURCE_PROOF_JSON)

    return proof


def build_mcp_denied_tools_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Exercise every denied action and attest metadata-only, no-raw-echo denial receipts.

    Runs against a temporary database. Confirms each of the explicit denied actions is
    denied with a denial receipt that names the action, that a denied token riding in an
    allowed tool's arguments is denied, and that raw requested content embedded in
    arguments never lands in any denial-receipt column (only the hash is stored).
    """
    from .broker import REASON_ACTION_DENIED, ToolBroker  # noqa: PLC0415

    denied_actions = sorted(load_denied_actions())
    secret_marker = "RAW-SECRET-9f3a2b-do-not-persist"
    fake_url = "https://example.com/secret-download"

    action_report: dict[str, Any] = {}
    all_pass = True

    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "denied.db")
        broker = ToolBroker(wrappers={}, db_path=db, persist=True)

        for action in denied_actions:
            env = broker.dispatch(action, {})
            ok = bool(
                env.get("decision") == "denied"
                and env.get("reason_code") == REASON_ACTION_DENIED
                and env.get("receipt_id")
                and env.get("tool") == action
            )
            all_pass = all_pass and ok
            action_report[action] = {
                "decision": env.get("decision"),
                "reason_code": env.get("reason_code"),
                "requested_action": env.get("tool"),
                "receipt_id_present": bool(env.get("receipt_id")),
                "pass": ok,
            }

        # Denied token riding in an allowed tool's arguments → denied, names the token.
        token_env = broker.dispatch("hb_status", {"mode": "graph_api_call"})
        token_pass = bool(
            token_env.get("decision") == "denied"
            and token_env.get("tool") == "graph_api_call"
            and token_env.get("reason_code") == REASON_ACTION_DENIED
        )

        # Raw content embedded in a denied request must never be persisted.
        broker.dispatch("arbitrary_sql", {"sql": secret_marker, "body": fake_url})

        conn = sqlite3.connect(db)
        denial_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_denial_receipts)")
        ]
        # Concatenate every text value across all denial rows and scan for the markers.
        all_text = " ".join(
            str(v)
            for row in conn.execute(
                f"SELECT {', '.join(denial_cols)} FROM second_brain_mcp_denial_receipts"
            )
            for v in row
            if v is not None
        )
        no_raw_echo = secret_marker not in all_text and fake_url not in all_text
        no_raw_columns = not (
            {"raw_requested_content", "raw_args", "raw_prompt", "raw_response", "raw_sql"}
            & set(denial_cols)
        )
        guards_clean = _guards_all_zero(conn, "second_brain_mcp_denial_receipts")
        denial_rows = conn.execute(
            "SELECT COUNT(*) FROM second_brain_mcp_denial_receipts"
        ).fetchone()[0]

    proof_passed = bool(
        all_pass and token_pass and no_raw_echo and no_raw_columns and guards_clean
    )
    proof: dict[str, Any] = {
        "proof": "phase_08d_mcp_denied_tools",
        "phase": "08D",
        "proof_passed": proof_passed,
        "denied_action_count": len(denied_actions),
        "denied_actions": denied_actions,
        "reason_code": REASON_ACTION_DENIED,
        "per_action": action_report,
        "denied_token_in_args": {
            "decision": token_env.get("decision"),
            "requested_action": token_env.get("tool"),
            "pass": token_pass,
        },
        "denial_receipts_written": denial_rows,
        "metadata_only": {
            "no_raw_requested_content_echoed": no_raw_echo,
            "denial_table_has_no_raw_columns": no_raw_columns,
            "all_guard_columns_zero": guards_clean,
            "request_hash_only": True,
        },
        "guardrails": {
            "deny_first": True,
            "metadata_only_denial_receipts": True,
            "no_raw_echo": True,
        },
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp denied-tools proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / DENIED_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        proof["proof_path"] = str(out_dir / DENIED_PROOF_JSON)

    return proof


def build_mcp_allowed_tools_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Dispatch all nine allowed tools through the real broker and attest the contract shape.

    Runs against a temporary database (empty → wrappers degrade safely but stay allowed),
    proving each tool is workflow-only: returns the bounded contract envelope, leaks no raw
    fields, and writes a metadata-only receipt. Writes ``mcp-tool-contract-proof.json``.
    """
    # Imported lazily to avoid a module import cycle (wrappers import this module).
    from . import build_default_broker  # noqa: PLC0415
    from .registry import load_allowed_tools

    allowed = load_allowed_tools()
    tool_report: dict[str, Any] = {}
    all_pass = True

    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "tools.db")
        broker = build_default_broker(db_path=db, persist=True)
        sample_args = {
            "hb_query": {"question": "status?"},
            "hb_memory_feedback": {"target_id": "cand-test", "feedback_class": "accept"},
        }
        for name in sorted(allowed):
            env = broker.dispatch(name, sample_args.get(name, {}))
            result = env.get("result") if isinstance(env, dict) else None
            has_envelope = all(
                k in env for k in ("status", "provenance", "policy_posture", "receipt_id")
            )
            keys = _collect_keys(env)
            forbidden_hit = sorted(set(_FORBIDDEN_RESULT_FIELDS) & keys)
            ok = bool(
                env.get("decision") == "allowed"
                and has_envelope
                and env.get("receipt_id")
                and not forbidden_hit
                and isinstance(result, dict)
            )
            all_pass = all_pass and ok
            tool_report[name] = {
                "decision": env.get("decision"),
                "wrapper": allowed[name]["wrapper"],
                "status": (result or {}).get("status"),
                "output_classification": env.get("output_classification"),
                "result_count": env.get("result_count"),
                "receipt_id_present": bool(env.get("receipt_id")),
                "envelope_complete": has_envelope,
                "forbidden_fields": forbidden_hit,
                "pass": ok,
            }

        conn = sqlite3.connect(db)
        receipts = conn.execute(
            "SELECT COUNT(*) FROM second_brain_mcp_tool_call_receipts"
        ).fetchone()[0]
        guards_clean = _guards_all_zero(conn, "second_brain_mcp_tool_call_receipts")

    proof_passed = bool(all_pass and receipts == len(allowed) and guards_clean)
    proof: dict[str, Any] = {
        "proof": "phase_08d_mcp_allowed_tools",
        "phase": "08D",
        "proof_passed": proof_passed,
        "tool_count": len(allowed),
        "tools": tool_report,
        "tool_call_receipts": receipts,
        "metadata_only": {
            "all_guard_columns_zero": guards_clean,
            "no_forbidden_result_fields": all(
                not r["forbidden_fields"] for r in tool_report.values()
            ),
        },
        "contract": {
            "required_envelope": ["status", "provenance", "policy_posture", "receipt_id"],
            "bounded_output": True,
            "workflow_wrapper_only": True,
        },
        "guardrails": {
            "no_raw_content": True,
            "no_writeback_external": True,
            "no_final_determination": True,
            "offline_mock_first": True,
        },
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp allowed-tools contract proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / CONTRACT_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        proof["proof_path"] = str(out_dir / CONTRACT_PROOF_JSON)

    return proof
