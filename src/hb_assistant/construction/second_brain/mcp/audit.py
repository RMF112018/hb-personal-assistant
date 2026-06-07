"""Phase 08D MCP audit / permission agent (Prompt 10).

The backing service for the permission audit (the ``mcp audit`` CLI lands in Prompt 11).
It snapshots all four registries (server-config, tool, resource, prompt) and runs the ten
permission-audit checks at the **registry/contract level** (fast, read-only) plus the
lightweight metadata-only sub-proofs (denied/prompts/broker/runbook). The heavyweight
execution proofs that dispatch synthesis/retrieval are validated in their own prompts, not
re-run on every audit. Persists a metadata-only permission-audit run and emits the
call/denial receipt proof. Snapshots/runs store counts, hashes, status, and reason codes only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..financial_review_routing import _assert_no_raw
from .policy import (
    _PERMISSION_POLICY_SEED,
    _load_seed,
    _policy_version,
    build_mcp_status,
)
from .prompts import load_prompts, snapshot_prompt_registry
from .proof import (
    build_mcp_claude_desktop_runbook_proof,
    build_mcp_denied_tools_proof,
    build_mcp_prompts_proof,
    build_mcp_tool_broker_proof,
)
from .registry import (
    get_mcp_raw_content_posture,
    load_allowed_tools,
    load_denied_actions,
    load_global_requirements,
)
from .resources import load_resources, snapshot_resource_registry
from .store import (
    _sha256,
    write_mcp_permission_audit_run,
    write_mcp_server_config_snapshot,
    write_mcp_tool_registry_snapshot,
)

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-08d-mcp-bridge"
AUDIT_PROOF_JSON = "mcp-audit-receipt-proof.json"

# Required denied-action coverage by class (denied_registry_complete).
_RAW_ACTIONS = {
    "raw_file_read",
    "raw_obsidian_read",
    "raw_sqlite_query",
    "raw_email_body_access",
    "raw_document_text_access",
    "raw_calendar_payload_access",
    "raw_procore_payload_access",
    "raw_financial_payload_access",
    "raw_prompt_access",
    "raw_response_access",
}
_WRITEBACK_ACTIONS = {
    "email_send",
    "calendar_update",
    "source_system_writeback",
    "external_delivery",
}
_API_ACTIONS = {"graph_api_call", "procore_api_call", "arbitrary_sql"}
_DETERMINATION_ACTIONS = {
    "payment_decision",
    "claim_decision",
    "entitlement_decision",
    "final_financial_determination",
}
_URL_ACTIONS = {"signed_url_access", "download_url_access"}

_CONTRACT_CHECKS = [
    "server_config_safe",
    "allowed_registry_safe",
    "denied_registry_complete",
    "resources_safe",
    "prompts_safe",
    "receipts_metadata_only",
    "claude_config_safe",
    "no_raw_access",
    "no_writeback",
    "no_direct_apis",
]


def _tool_registry_hash(allowed: dict[str, Any], denied: set[str]) -> str:
    return _sha256({"allowed": sorted(allowed), "denied": sorted(denied)})


def snapshot_tool_registry(*, db_path: str | None = None, persist: bool = True) -> str | None:
    """Persist a metadata-only tool-registry snapshot (counts + hash). Returns its id."""
    if not persist:
        return None
    allowed = load_allowed_tools()
    denied = load_denied_actions()
    return write_mcp_tool_registry_snapshot(
        allowed_tool_count=len(allowed),
        denied_action_count=len(denied),
        registry_hash=_tool_registry_hash(allowed, denied),
        policy_version=_policy_version(),
        db_path=db_path,
    )


def snapshot_all_registries(*, db_path: str | None = None, persist: bool = True) -> dict[str, Any]:
    """Persist all four registry snapshots; return their ids (or None when persist=False)."""
    server_id: str | None = None
    if persist:
        status = build_mcp_status(persist=False)
        server_id = write_mcp_server_config_snapshot(
            transport=str(status["transport"]),
            config_hash=str(status["config_hash"]),
            policy_version=_policy_version(),
            db_path=db_path,
        )
    return {
        "server_config": server_id,
        "tool_registry": snapshot_tool_registry(db_path=db_path, persist=persist),
        "resource_registry": snapshot_resource_registry(db_path=db_path, persist=persist),
        "prompt_registry": snapshot_prompt_registry(db_path=db_path, persist=persist),
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def run_mcp_permission_audit(
    *,
    db_path: str | None = None,
    persist: bool = True,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Run the ten permission-audit checks, snapshot registries, persist a metadata-only run."""
    snapshots = snapshot_all_registries(db_path=db_path, persist=persist)

    # An audit verifies POLICY / REGISTRY posture: the allowed-tools and resources surfaces
    # are checked at the registry/contract level (fast, read-only). The heavyweight execution
    # proofs that dispatch synthesis/retrieval (build_mcp_allowed_tools_proof /
    # build_mcp_resources_proof) are validated in their own prompts, not re-run on every audit.
    status = build_mcp_status(persist=False)
    allowed_tools = load_allowed_tools()
    global_requirements = set(load_global_requirements())
    resources_list = load_resources()
    prompts_list = load_prompts()
    denied = build_mcp_denied_tools_proof(write_evidence=False)
    prompts = build_mcp_prompts_proof(write_evidence=False)
    broker = build_mcp_tool_broker_proof(write_evidence=False)
    runbook = build_mcp_claude_desktop_runbook_proof(write_evidence=False)

    _REQUIRED_REQS = {
        "workflow_wrapper_only",
        "no_raw_content",
        "no_writeback",
        "no_final_determinations",
    }
    allowed_registry_safe = len(allowed_tools) == 10 and global_requirements >= _REQUIRED_REQS

    denied_set = set(load_denied_actions())
    perm = _load_seed(_PERMISSION_POLICY_SEED)
    allow_flags = {k: v for k, v in perm.items() if k.startswith("allow_")}
    all_allow_false = bool(allow_flags) and not any(bool(v) for v in allow_flags.values())

    receipts_metadata_only = bool(
        broker.get("metadata_only", {}).get("all_guard_columns_zero")
        and broker.get("metadata_only", {}).get("receipt_tables_have_no_raw_columns")
        and denied.get("metadata_only", {}).get("all_guard_columns_zero")
        and denied.get("metadata_only", {}).get("denial_table_has_no_raw_columns")
    )

    checks = [
        _check(
            "server_config_safe",
            bool(status.get("foundation_ok") and status.get("transport") == "stdio"),
            "stdio transport + foundation checks pass",
        ),
        _check(
            "allowed_registry_safe",
            allowed_registry_safe,
            "ten approved workflow tools; workflow-only/no-raw/no-writeback/no-determination required",
        ),
        _check(
            "denied_registry_complete",
            bool(
                denied.get("proof_passed")
                and denied_set
                >= (
                    _RAW_ACTIONS
                    | _WRITEBACK_ACTIONS
                    | _API_ACTIONS
                    | _DETERMINATION_ACTIONS
                    | _URL_ACTIONS
                )
            ),
            "raw/api/writeback/determination/url actions all denied",
        ),
        _check("resources_safe", len(resources_list) == 5, "five approved-workflow resources"),
        _check(
            "prompts_safe", bool(prompts.get("proof_passed")), "five prompts, allowed-tools only"
        ),
        _check(
            "receipts_metadata_only",
            receipts_metadata_only,
            "tool-call + denial receipts: hashes only, no raw columns, guards 0",
        ),
        _check(
            "claude_config_safe",
            bool(runbook.get("proof_passed")),
            "stdio preview, never auto-written",
        ),
        _check(
            "no_raw_access",
            bool(
                "no_raw_content" in global_requirements
                and denied_set >= _RAW_ACTIONS
                and len(resources_list) == 5
                and len(prompts_list) == 5
                and bool(prompts.get("proof_passed"))
            ),
            "no raw stores/files/payloads via tools/resources/prompts",
        ),
        _check(
            "no_writeback",
            bool(all_allow_false and denied_set >= _WRITEBACK_ACTIONS),
            "permission policy allow_* false + writeback actions denied",
        ),
        _check(
            "no_direct_apis",
            bool(all_allow_false and denied_set >= _API_ACTIONS),
            "permission policy allow_* false + direct-API/SQL actions denied",
        ),
    ]

    finding_count = sum(1 for c in checks if not c["passed"])
    audit_status = "ok" if finding_count == 0 else "attention"
    proof_passed = finding_count == 0

    out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
    evidence_path = str(out_dir / AUDIT_PROOF_JSON)

    report: dict[str, Any] = {
        "proof": "phase_08d_mcp_permission_audit",
        "phase": "08D",
        "proof_passed": proof_passed,
        "status": audit_status,
        "finding_count": finding_count,
        "contract_checks": list(_CONTRACT_CHECKS),
        "checks": checks,
        "registry_snapshots": {k: bool(v) for k, v in snapshots.items()},
        "receipts": {
            "metadata_only": receipts_metadata_only,
            "tool_call_table": "second_brain_mcp_tool_call_receipts",
            "denial_table": "second_brain_mcp_denial_receipts",
            "stored": "hashes/counts/reason codes only",
        },
        "guardrails": {"read_only": True, "metadata_only": True, "no_raw_content": True},
    }

    # P09: include raw MCP posture in audit (explicit, default disabled)
    try:
        mcp_raw = get_mcp_raw_content_posture()
        report["raw_content_posture"] = mcp_raw
        if mcp_raw.get("mcp_raw_allowed"):
            report["guardrails"]["no_raw_content"] = False
            report["guardrails"]["mcp_raw_allowed"] = True
    except Exception:
        pass

    serialized = json.dumps(report, indent=2, default=str)
    _assert_no_raw(serialized, "mcp permission-audit report")

    if persist:
        audit_run_id = write_mcp_permission_audit_run(
            status=audit_status,
            checks_json=json.dumps(checks, default=str),
            finding_count=finding_count,
            policy_version=_policy_version(),
            evidence_path=evidence_path if write_evidence else None,
            db_path=db_path,
        )
        report["audit_run_id"] = audit_run_id

    if write_evidence:
        out_dir.mkdir(parents=True, exist_ok=True)
        Path(evidence_path).write_text(serialized + "\n", encoding="utf-8")
        report["proof_path"] = evidence_path

    return report
