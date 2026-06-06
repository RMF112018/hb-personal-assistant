"""Phase 09 Addendum — MCP daily-brief handoff tool proof.

Proves the narrow ``hb_daily_brief_packet`` MCP workflow-wrapper tool: it is registered in the allowed
registry, dispatches through the real broker to return a ``DailyBriefHandoffPacketV2`` (render_payload
/ governance_metadata split) that matches the V2 packet contract — render carries the required
sections, governance carries the required metadata, and no governance key leaks into render_payload —
is read-only / metadata-only / no-raw, exposes no direct DB/vector/Graph/Procore/memory-mutation/
writeback path (deny-first preserved), fails safe on missing inputs, and leaves the MCP no-raw /
no-writeback proofs green. Read-only; runs against a temporary seeded DB; persists nothing to the
operator DB.

Public entry point:
  build_mcp_daily_brief_handoff_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain mcp daily-brief-handoff-proof --json
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff"
_PROOF_JSON = "mcp-daily-brief-handoff-proof.json"
_PROOF_MD = "mcp-daily-brief-handoff-proof.md"

TOOL_NAME = "hb_daily_brief_packet"
WRAPPER_NAME = "mcp_daily_brief_packet_wrapper"

# Representative deny-first checks: explicit denied actions + not-allowed tool names that must never
# be exposed (vector search, memory mutation, daily-brief apply) + a denied token riding in args.
_DENIED_ACTIONS = (
    "arbitrary_sql",
    "raw_sqlite_query",
    "graph_api_call",
    "procore_api_call",
    "source_system_writeback",
    "raw_file_read",
)
_NOT_ALLOWED_TOOLS = (
    "vector_index_search",
    "memory_accept",
    "daily_brief_apply",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — MCP Daily Brief Handoff Tool Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- tool: {proof['tool']}",
        f"- tool_registered: {proof['tool_registered']}",
        f"- dispatch_allowed: {proof['dispatch_allowed']}",
        f"- output_matches_contract: {proof['output_matches_contract']}",
        f"- items_match_contract: {proof['items_match_contract']}",
        f"- packet_version_ok: {proof['packet_version_ok']}",
        f"- no_raw_emitted: {proof['no_raw_emitted']}",
        f"- no_forbidden_result_fields: {proof['no_forbidden_result_fields']}",
        f"- read_only_no_writeback: {proof['read_only_no_writeback']}",
        f"- missing_inputs_fail_safe: {proof['missing_inputs_fail_safe']}",
        f"- deny_first_preserved: {proof['deny_first_preserved']}",
        f"- mcp_no_raw_proof_passed: {proof['mcp_no_raw_proof_passed']}",
        f"- mcp_no_writeback_proof_passed: {proof['mcp_no_writeback_proof_passed']}",
        "",
        "## Deny-first checks",
        "",
    ]
    for action, denied in proof["denied_checks"].items():
        lines.append(f"- {action}: denied={denied}")
    lines.append("")
    return "\n".join(lines)


def build_mcp_daily_brief_handoff_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof for the ``hb_daily_brief_packet`` MCP tool (read-only)."""
    from ..daily_brief.packet import _seed_proof_db, load_daily_brief_packet_v2_contract
    from . import build_default_broker
    from .proof import (
        _FORBIDDEN_RESULT_FIELDS,
        _collect_keys,
        build_no_mcp_writeback_proof,
        build_no_raw_mcp_access_proof,
    )
    from .registry import load_allowed_tools

    allowed = load_allowed_tools()
    tool_registered = TOOL_NAME in allowed and allowed[TOOL_NAME].get("wrapper") == WRAPPER_NAME

    contract = load_daily_brief_packet_v2_contract()
    render_sections = list(contract.get("render_payload_sections", []))
    governance_fields = list(contract.get("governance_metadata_fields", []))
    forbidden_in_render = list(contract.get("forbidden_in_render_payload", []))

    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "seeded.sqlite3")
        _seed_proof_db(db)
        broker = build_default_broker(db_path=db, persist=True)

        env = broker.dispatch(TOOL_NAME, {"date": "2026-06-02", "project_scope": "P1"})
        dispatch_allowed = env.get("decision") == "allowed"
        result = env.get("result") if isinstance(env, dict) else None
        results_list = (result or {}).get("results") or []
        packet = results_list[0] if results_list else {}

        render = packet.get("render_payload", {}) if isinstance(packet, dict) else {}
        governance = packet.get("governance_metadata", {}) if isinstance(packet, dict) else {}
        # V2 contract: render carries the required sections, governance carries the required
        # metadata, and no governance key leaks into the render body.
        output_matches_contract = (
            isinstance(render, dict)
            and isinstance(governance, dict)
            and all(s in render for s in render_sections)
            and all(f in governance for f in governance_fields)
            and not any(k in render for k in forbidden_in_render)
        )
        # Renderable items remain source-linked (hashed refs only).
        items = render.get("needs_attention", []) if isinstance(render, dict) else []
        items_match = bool(items) and all(
            bool(it.get("source_family")) and bool(it.get("source_ref_hash")) for it in items
        )
        packet_version_ok = governance.get("packet_version") == "DailyBriefHandoffPacketV2"

        try:
            _assert_no_raw(json.dumps(env, default=str), "mcp daily brief handoff tool output")
            no_raw_emitted = True
        except ValueError:
            no_raw_emitted = False
        forbidden_hit = sorted(set(_FORBIDDEN_RESULT_FIELDS) & _collect_keys(env))
        no_forbidden_fields = not forbidden_hit

        # Read-only: the tool/build never persisted a daily-brief run; a metadata-only call receipt is.
        conn = sqlite3.connect(db)
        try:
            brief_runs = conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0]
            tool_receipts = conn.execute(
                "SELECT COUNT(*) FROM second_brain_mcp_tool_call_receipts WHERE tool_name = ?",
                (TOOL_NAME,),
            ).fetchone()[0]
        finally:
            conn.close()
        read_only_no_writeback = brief_runs == 0 and tool_receipts >= 1

        # Missing date/project scope still routes safely (allowed; never raw).
        env_empty = broker.dispatch(TOOL_NAME, {})
        missing_inputs_fail_safe = env_empty.get("decision") == "allowed"

        # Deny-first preserved: no direct DB/vector/Graph/Procore/memory/writeback path.
        denied_checks: dict[str, bool] = {}
        for action in _DENIED_ACTIONS + _NOT_ALLOWED_TOOLS:
            denied_checks[action] = broker.dispatch(action, {}).get("decision") == "denied"
        denied_checks["denied_token_in_args"] = (
            broker.dispatch(TOOL_NAME, {"q": "graph_api_call"}).get("decision") == "denied"
        )
        deny_first_preserved = all(denied_checks.values())

    # Sibling guard proofs remain green after adding the tool.
    no_raw_proof = build_no_raw_mcp_access_proof(write_evidence=False)
    no_writeback_proof = build_no_mcp_writeback_proof(write_evidence=False)
    mcp_no_raw_passed = bool(no_raw_proof.get("proof_passed"))
    mcp_no_writeback_passed = bool(no_writeback_proof.get("proof_passed"))

    proof_passed = all(
        [
            tool_registered,
            dispatch_allowed,
            output_matches_contract,
            items_match,
            packet_version_ok,
            no_raw_emitted,
            no_forbidden_fields,
            read_only_no_writeback,
            missing_inputs_fail_safe,
            deny_first_preserved,
            mcp_no_raw_passed,
            mcp_no_writeback_passed,
        ]
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_mcp_daily_brief_handoff_tool",
        "command": "second-brain mcp daily-brief-handoff-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "tool": TOOL_NAME,
        "wrapper": WRAPPER_NAME,
        "packet_version": "DailyBriefHandoffPacketV2",
        "tool_registered": tool_registered,
        "dispatch_allowed": dispatch_allowed,
        "output_matches_contract": output_matches_contract,
        "items_match_contract": items_match,
        "packet_version_ok": packet_version_ok,
        "no_raw_emitted": no_raw_emitted,
        "no_forbidden_result_fields": no_forbidden_fields,
        "forbidden_fields": forbidden_hit,
        "read_only_no_writeback": read_only_no_writeback,
        "missing_inputs_fail_safe": missing_inputs_fail_safe,
        "deny_first_preserved": deny_first_preserved,
        "denied_checks": denied_checks,
        "mcp_no_raw_proof_passed": mcp_no_raw_passed,
        "mcp_no_writeback_proof_passed": mcp_no_writeback_passed,
        "metadata_only": True,
        "guardrails": {
            "workflow_wrapper_only": True,
            "read_only": True,
            "local_first": True,
            "metadata_only": True,
            "source_linked": True,
            "no_raw": True,
            "no_writeback": True,
            "no_final_determination": True,
            "no_direct_graph_procore_db_vector": True,
            "deny_first_preserved": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "mcp daily brief handoff proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "mcp daily brief handoff proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
