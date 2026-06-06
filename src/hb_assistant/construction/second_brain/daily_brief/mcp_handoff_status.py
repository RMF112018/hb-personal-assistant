"""Phase 09 Addendum — daily-brief MCP handoff operator status (closeout integration).

Surfaces the daily-brief handoff chain (packet → MCP tool → render templates → rendered quality →
output receipt) as an honest, advisory-only operator status: the five handoff status fields, gate
dispositions (handoff is not a production blocker except for closeout-blocking safety/handoff proofs),
the distinguished `substrate_detail`, and a `status_label_reconciliation` block that resolves the
historical `phase_09_substrate_status` drift between phase-09-gates and phase-09-operator-status.

Read-only, metadata-only; never overstates readiness (production_readiness=false). All heavy imports are
lazy to avoid import cycles (phase-09-gates / operator-status lazy-import `handoff_present` from here).

Public entry points:
  handoff_present(db_path=None) -> bool
  build_daily_brief_mcp_handoff_status(*, db_path=None, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain daily-brief mcp-handoff-status --json
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..financial_review_routing import _assert_no_raw
from ..phase_09_schema import QUALITY_SUBSTRATE_TABLES, compute_substrate_detail

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff"
_STATUS_JSON = "daily-brief-mcp-handoff-operator-status.json"
_STATUS_MD = "daily-brief-mcp-handoff-operator-status.md"

_HANDOFF_TOOL = "hb_daily_brief_packet"


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


def handoff_present(db_path: str | None = None) -> bool:
    """Cheap presence check (no temp DB): packet contract loads + the MCP handoff tool is registered."""
    try:
        from ..mcp.registry import load_allowed_tools
        from .packet import load_daily_brief_packet_contract

        load_daily_brief_packet_contract()
        return _HANDOFF_TOOL in load_allowed_tools()
    except Exception:
        return False


def _gate(
    name: str, status: str, *, blocking: int = 0, reason: str | None = None
) -> dict[str, Any]:
    return {"gate_name": name, "gate_status": status, "blocking": blocking, "reason": reason}


def _count_statuses(gates: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warning": 0, "fail_blocking": 0, "deferred_not_blocking": 0}
    for g in gates:
        counts[str(g["gate_status"])] = counts.get(str(g["gate_status"]), 0) + 1
    return counts


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Daily Brief MCP Handoff Operator Status",
        "",
        f"- generated_utc: {report['generated_utc']}",
        f"- handoff_closeout_ok: {report['handoff_closeout_ok']}",
        f"- production_readiness: {report['readiness_categories']['production_readiness']}",
        f"- readiness_overstated: {report['readiness_overstated']}",
        "",
        "## Handoff status fields",
        "",
        f"- daily_brief_packet_status: {report['daily_brief_packet_status']}",
        f"- daily_brief_mcp_handoff_status: {report['daily_brief_mcp_handoff_status']}",
        f"- claude_rendering_template_status: {report['claude_rendering_template_status']}",
        f"- rendered_brief_quality_status: {report['rendered_brief_quality_status']}",
        f"- rendered_output_import_status: {report['rendered_output_import_status']}",
        "",
        "## Gates",
        "",
    ]
    for g in report["gates"]:
        lines.append(
            f"- {g['gate_name']}: {g['gate_status']}" + (f" ({g['reason']})" if g["reason"] else "")
        )
    lines.append("")
    lines.append("## Substrate detail (distinguished, reconciled)")
    lines.append("")
    for k, v in report["substrate_detail"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    rec = report["status_label_reconciliation"]
    lines.append("## Status-label reconciliation")
    lines.append("")
    lines.append(
        f"- phase-09-gates phase_09_substrate_status: {rec['phase_09_gates_substrate_status']}"
    )
    lines.append(
        f"- phase-09-operator-status phase_09_substrate_status: {rec['phase_09_operator_status_substrate_status']}"
    )
    lines.append(f"- {rec['explanation']}")
    lines.append("")
    return "\n".join(lines)


def build_daily_brief_mcp_handoff_status(
    *, db_path: str | None = None, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Build the daily-brief MCP handoff operator status (read-only, advisory, never overstated)."""
    # --- packet status ---
    try:
        from .packet import build_daily_brief_packet_proof, load_daily_brief_packet_contract

        load_daily_brief_packet_contract()
        packet_contract_ok = True
        try:
            packet_validated = bool(
                build_daily_brief_packet_proof(write_evidence=False).get("proof_passed")
            )
        except Exception:
            packet_validated = False
        daily_brief_packet_status = "validated" if packet_validated else "available"
    except Exception:
        packet_contract_ok = False
        daily_brief_packet_status = "missing"

    # --- MCP no-raw / no-writeback (closeout-blocking) ---
    try:
        from ..mcp import build_no_mcp_writeback_proof, build_no_raw_mcp_access_proof

        no_raw_ok = bool(build_no_raw_mcp_access_proof(write_evidence=False).get("proof_passed"))
        no_writeback_ok = bool(
            build_no_mcp_writeback_proof(write_evidence=False).get("proof_passed")
        )
    except Exception:
        no_raw_ok = False
        no_writeback_ok = False
    safety_ok = no_raw_ok and no_writeback_ok

    # --- MCP handoff tool status ---
    try:
        from ..mcp.registry import load_allowed_tools

        tool_registered = _HANDOFF_TOOL in load_allowed_tools()
    except Exception:
        tool_registered = False

    handoff_proof_passed = False
    if not tool_registered:
        daily_brief_mcp_handoff_status = "missing"
    elif not safety_ok:
        daily_brief_mcp_handoff_status = "blocked"
    else:
        try:
            from ..mcp import build_mcp_daily_brief_handoff_proof

            handoff_proof_passed = bool(
                build_mcp_daily_brief_handoff_proof(write_evidence=False).get("proof_passed")
            )
        except Exception:
            handoff_proof_passed = False
        daily_brief_mcp_handoff_status = "proof_passed" if handoff_proof_passed else "available"

    # --- Claude rendering template status ---
    try:
        from ..mcp.render_template_proof import (
            ClaudeRenderTemplateError,
            build_claude_render_template_proof,
        )

        try:
            tmpl_passed = bool(
                build_claude_render_template_proof(write_evidence=False).get("proof_passed")
            )
            claude_rendering_template_status = "validated" if tmpl_passed else "available"
        except ClaudeRenderTemplateError:
            claude_rendering_template_status = "missing"
    except Exception:
        claude_rendering_template_status = "missing"

    # --- rendered brief quality status ---
    try:
        from .rendered_quality import build_daily_brief_rendered_quality_proof

        rq_passed = bool(
            build_daily_brief_rendered_quality_proof(write_evidence=False).get("proof_passed")
        )
        rendered_brief_quality_status = "proof_passed" if rq_passed else "proof_failed"
    except Exception:
        rendered_brief_quality_status = "not_run"

    # --- rendered output import status (deferred by policy) ---
    try:
        from .output_receipt import IMPORT_ENABLED

        rendered_output_import_status = "reviewed_only" if IMPORT_ENABLED else "deferred"
    except Exception:
        rendered_output_import_status = "not_supported"

    # --- gate dispositions (handoff is not a production blocker; only safety + handoff proof block) ---
    gates: list[dict[str, Any]] = [
        _gate(
            "packet_contract",
            "pass" if packet_contract_ok else "deferred_not_blocking",
            reason=None if packet_contract_ok else "PACKET_CONTRACT_MISSING",
        ),
        _gate(
            "mcp_handoff_proof",
            "pass" if handoff_proof_passed else "fail_blocking",
            blocking=0 if handoff_proof_passed else 1,
            reason=None if handoff_proof_passed else "HANDOFF_PROOF_FAILED",
        ),
        _gate(
            "no_raw_no_writeback",
            "pass" if safety_ok else "fail_blocking",
            blocking=0 if safety_ok else 1,
            reason=None if safety_ok else "MCP_SAFETY_PROOF_FAILED",
        ),
    ]
    if rendered_brief_quality_status == "proof_passed":
        gates.append(_gate("rendered_quality", "pass"))
    elif rendered_brief_quality_status == "not_run":
        gates.append(
            _gate("rendered_quality", "deferred_not_blocking", reason="RENDERED_QUALITY_NOT_RUN")
        )
    else:
        gates.append(_gate("rendered_quality", "warning", reason="RENDERED_QUALITY_FAILED"))
    gates.append(
        _gate("rendered_output_import", "deferred_not_blocking", reason="IMPORT_DEFERRED_EXPECTED")
    )

    status_counts = _count_statuses(gates)
    handoff_closeout_ok = status_counts["fail_blocking"] == 0

    # --- distinguished substrate detail (shared shape; handoff substrate from proof state) ---
    try:
        from ..phase_09_schema import build_phase_09_schema_status_report

        schema_report = build_phase_09_schema_status_report(db_path)
        row_counts = {
            str(t["table_name"]): t.get("row_count") for t in schema_report.get("tables", [])
        }
        schema_ready = bool(
            schema_report.get("schema_ready")
            and schema_report.get("all_tables_present")
            and schema_report.get("all_guards_present")
        )
    except Exception:
        row_counts = {}
        schema_ready = False
    try:
        from ..corpus_balance_mart import build_coverage_parity_report

        coverage_ok = bool(build_coverage_parity_report(db_path).get("coverage_parity_ok"))
    except Exception:
        coverage_ok = False

    substrate_detail = compute_substrate_detail(
        schema_ready=schema_ready,
        coverage_ok=coverage_ok,
        quality_row_counts={t: row_counts.get(t) for t in QUALITY_SUBSTRATE_TABLES},
        handoff_present=(tool_registered and packet_contract_ok),
    )
    substrate_detail["handoff_substrate"] = (
        "proof_passed"
        if handoff_proof_passed
        else ("available" if (tool_registered and packet_contract_ok) else "missing")
    )

    # --- reconcile the historical drift between the two core commands ---
    try:
        from ..phase_09_gates import build_phase_09_gates_proof

        gates_substrate = build_phase_09_gates_proof(db_path=db_path, write_evidence=False).get(
            "phase_09_substrate_status"
        )
    except Exception:
        gates_substrate = None
    try:
        from ..phase_09_operator_status import evaluate_phase_09_operator_status

        operator_substrate = evaluate_phase_09_operator_status(db_path=db_path).get(
            "phase_09_substrate_status"
        )
    except Exception:
        operator_substrate = None

    status_label_reconciliation = {
        "phase_09_gates_substrate_status": gates_substrate,
        "phase_09_operator_status_substrate_status": operator_substrate,
        "explanation": (
            "The two core commands historically used the same field name for different substrates: "
            "phase-09-gates reports quality-surface emptiness (advisory_empty until quality tables "
            "populate), while phase-09-operator-status reports any-table population. The distinguished "
            "substrate_detail block is the reconciled canonical view; both core commands now also emit it."
        ),
        "reconciled_substrate_detail": substrate_detail,
    }

    report: dict[str, Any] = {
        "command": "second-brain daily-brief mcp-handoff-status",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "daily_brief_packet_status": daily_brief_packet_status,
        "daily_brief_mcp_handoff_status": daily_brief_mcp_handoff_status,
        "claude_rendering_template_status": claude_rendering_template_status,
        "rendered_brief_quality_status": rendered_brief_quality_status,
        "rendered_output_import_status": rendered_output_import_status,
        "gates": gates,
        "status_counts": status_counts,
        "handoff_closeout_ok": handoff_closeout_ok,
        "substrate_detail": substrate_detail,
        "status_label_reconciliation": status_label_reconciliation,
        "advisory_only": True,
        "makes_determination": False,
        "read_only": True,
        "readiness_overstated": False,
        "readiness_categories": {
            "handoff_substrate_ready": bool(handoff_proof_passed and safety_ok),
            "production_readiness": False,
            "deferred_limitations": [
                "rendered narrative is advisory/not source truth; excluded from trusted stores",
                "rendered-output import deferred (reviewed-import workflow not implemented)",
                "phase is not production-ready (advisory-only)",
            ],
        },
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_raw": True,
            "no_external_writeback": True,
            "advisory_only": True,
            "no_determination": True,
            "no_readiness_overstatement": True,
            "no_raw_no_writeback_blocking": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(report, indent=2, default=str)
        _assert_no_raw(serialized, "daily brief mcp handoff operator status json")
        (out_dir / _STATUS_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_md(report)
        _assert_no_raw(markdown, "daily brief mcp handoff operator status markdown")
        (out_dir / _STATUS_MD).write_text(markdown, encoding="utf-8")
        report["status_path"] = str(out_dir / _STATUS_JSON)
        report["status_md_path"] = str(out_dir / _STATUS_MD)

    return report
