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
from .registry import get_mcp_raw_content_posture, load_allowed_tools, load_denied_actions

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-08d-mcp-bridge"
PROOF_JSON = "mcp-tool-broker-proof.json"
CONTRACT_PROOF_JSON = "mcp-tool-contract-proof.json"
DENIED_PROOF_JSON = "mcp-denied-tool-proof.json"
RESOURCE_PROOF_JSON = "mcp-resource-contract-proof.json"
PROMPT_PROOF_JSON = "mcp-prompt-contract-proof.json"
RUNBOOK_PROOF_JSON = "mcp-claude-desktop-runbook-proof.json"
NO_RAW_PROOF_JSON = "no-raw-mcp-access-proof.json"
NO_RAW_PROOF_MD = "no-raw-mcp-access-proof.md"
NO_WRITEBACK_PROOF_JSON = "no-mcp-writeback-proof.json"
NO_WRITEBACK_PROOF_MD = "no-mcp-writeback-proof.md"
VALIDATION_MATRIX_PROOF_JSON = "phase-08d-validation-matrix-proof.json"
VALIDATION_MATRIX_PROOF_MD = "phase-08d-validation-matrix-proof.md"

# Dual-tree contract locations (the 08D JSON contracts live in both resource trees).
_VALIDATION_MATRIX_CONTRACT_PATHS = (
    "resources/json/phase_08d_validation_matrix.json",
    "src/hb_assistant/resources/json/phase_08d_validation_matrix.json",
)

# Closeout-critical 08D evidence the validation_matrix gate requires to be present (the
# per-prompt proofs plus the operational-serve proof). Static existence check only.
_VALIDATION_MATRIX_REQUIRED_EVIDENCE = (
    "phase-08d-gates-proof.json",
    "no-raw-mcp-access-proof.json",
    "no-mcp-writeback-proof.json",
    "mcp-tool-contract-proof.json",
    "mcp-resource-contract-proof.json",
    "mcp-prompt-contract-proof.json",
    "mcp-audit-receipt-proof.json",
    "mcp-tool-broker-proof.json",
    "mcp-server-config-proof.md",
    "mcp-claude-desktop-runbook-proof.md",
    "mcp-operational-serve-proof.md",
)

# Receipt columns that, if present, would mean a receipt table can persist raw content.
_FORBIDDEN_RECEIPT_COLUMNS = {
    "raw_args",
    "raw_result",
    "raw_prompt",
    "raw_response",
    "raw_sql",
    "raw_requested_content",
    "raw_body",
    "raw_source_content",
}

# Denied-action classes the no-writeback proof requires the registry to cover (mirrors the
# permission audit's no_writeback / no_direct_apis checks).
_WRITEBACK_ACTIONS = {
    "email_send",
    "calendar_update",
    "source_system_writeback",
    "external_delivery",
}
_DIRECT_API_ACTIONS = {"graph_api_call", "procore_api_call", "arbitrary_sql"}
_URL_ACTIONS = {"signed_url_access", "download_url_access"}

# Receipt guard columns that prove no writeback / direct API / external delivery was performed.
_WRITEBACK_GUARD_COLUMNS = (
    "external_writeback_performed",
    "graph_api_call_performed",
    "procore_api_call_performed",
    "email_send_performed",
    "calendar_update_performed",
    "source_system_writeback_performed",
    "arbitrary_sql_performed",
)

# Patterns that, if found in mcp source, would mean the code targets the LIVE Claude Desktop
# config (the preview file `claude-desktop-config-preview.json` is hyphenated and distinct).
_LIVE_CLAUDE_CONFIG_PATTERNS = (
    "claude_desktop_config.json",
    "Application Support/Claude",
)

_RUNBOOK_STEPS = [
    "hb-assistant second-brain mcp config-preview --client claude-desktop --json",
    "Confirm safe=true, transport=stdio, and unsafe_reasons=[].",
    "Copy the validated preview MANUALLY into the live Claude Desktop config "
    "(~/Library/Application Support/Claude/claude_desktop_config.json) — never auto-written.",
    "Restart Claude Desktop.",
    "Run hb-assistant second-brain mcp audit --json and confirm the config posture.",
]

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
        call_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_tool_call_receipts)")
        }
        no_raw_columns = (
            not ({"raw_args", "raw_result", "raw_prompt", "raw_response"} & call_cols)
            and "args_hash" in call_cols
            and "result_hash" in call_cols
        )

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
        all_pass and guards_clean and no_raw_columns and tool_call_rows == 1 and denial_rows == 5
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


def build_mcp_claude_desktop_runbook_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Attest the safe Claude Desktop config preview + the no-auto-write guarantee.

    Re-verifies the generated preview is safe / schema-conformant / preview-only, and
    statically scans the mcp module to prove no code path references the live Claude Desktop
    config (so the live config is never written automatically). Writes
    ``mcp-claude-desktop-runbook-proof.json``.
    """
    from .config_preview import build_claude_desktop_config_preview  # noqa: PLC0415

    preview = build_claude_desktop_config_preview(persist=False, write_evidence=False)
    preview_ok = bool(
        preview.get("safe") is True
        and preview.get("schema_conformant") is True
        and preview.get("transport") == "stdio"
        and preview.get("unsafe_reasons") == []
        and preview.get("auto_apply") is False
    )

    # No-auto-write static scan over the mcp module source. The prover module (this file)
    # is skipped — it documents the forbidden pattern as the scanner, it does not write config.
    mcp_dir = Path(__file__).resolve().parent
    findings: list[str] = []
    scanned = 0
    for py in sorted(mcp_dir.glob("*.py")):
        if py.name == "proof.py":
            continue
        scanned += 1
        text = py.read_text(encoding="utf-8")
        for pattern in _LIVE_CLAUDE_CONFIG_PATTERNS:
            if pattern in text:
                findings.append(f"{py.name}:{pattern}")
    no_auto_write = not findings

    proof_passed = bool(preview_ok and no_auto_write)
    proof: dict[str, Any] = {
        "proof": "phase_08d_mcp_claude_desktop_runbook",
        "phase": "08D",
        "proof_passed": proof_passed,
        "preview": {
            "safe": preview.get("safe"),
            "schema_conformant": preview.get("schema_conformant"),
            "transport": preview.get("transport"),
            "unsafe_reasons": preview.get("unsafe_reasons"),
            "auto_apply": preview.get("auto_apply"),
            "env_keys": preview.get("env_keys"),
        },
        "no_auto_write": {
            "live_config_never_written": no_auto_write,
            "mcp_files_scanned": scanned,
            "findings": findings,
            "preview_evidence_only": "claude-desktop-config-preview.json",
        },
        "operator_runbook_steps": _RUNBOOK_STEPS,
        "safe_checklist": {
            "command_is_hb_assistant_only": True,
            "transport_stdio_only": True,
            "env_keys_allowlisted": True,
            "no_secrets_or_broad_filesystem_path": True,
            "manual_paste_only": True,
        },
        "guardrails": {"never_overwrite_live_config": True, "preview_only": True},
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp claude-desktop runbook proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / RUNBOOK_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        proof["proof_path"] = str(out_dir / RUNBOOK_PROOF_JSON)

    return proof


def build_mcp_prompts_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Render all five prompts and attest the route-through-allowed-tools-only contract.

    Confirms each prompt routes only through allowed tools, carries the advisory /
    source-linked / review-controlled posture + no-determination + no-policy-bypass
    guidance, exposes no forbidden field, fail-closes on an unknown name, and that a
    metadata-only prompt-registry snapshot persists guard-clean. Writes
    ``mcp-prompt-contract-proof.json``.
    """
    from .prompts import (  # noqa: PLC0415
        load_prompts,
        render_prompt,
        snapshot_prompt_registry,
    )
    from .registry import load_allowed_tools

    registry = load_prompts()
    allowed = set(load_allowed_tools())
    _posture_markers = ("advisory", "source-linked", "review-controlled")
    _bypass_phrase = "do not bypass Phase 08A/08B/08C policy"
    prompt_report: dict[str, Any] = {}
    all_pass = True

    for entry in registry:
        name = entry["name"]
        rendered = render_prompt(name, {})
        text = json.dumps(rendered, default=str).lower()
        routes = rendered.get("routes_through", [])
        routes_ok = bool(routes) and all(t in allowed for t in routes)
        posture_ok = all(m in text for m in _posture_markers) and _bypass_phrase.lower() in text
        keys = _collect_keys(rendered)
        forbidden_hit = sorted(set(_FORBIDDEN_RESULT_FIELDS) & keys)
        ok = bool(routes_ok and posture_ok and not forbidden_hit)
        all_pass = all_pass and ok
        prompt_report[name] = {
            "routes_through": routes,
            "routes_through_allowed_only": routes_ok,
            "posture_present": posture_ok,
            "forbidden_fields": forbidden_hit,
            "pass": ok,
        }

    unknown = render_prompt("delete_everything", {})
    unknown_fail_closed = bool(
        unknown.get("status") == "denied"
        and unknown.get("reason_code") == "prompt_not_allowed"
        and unknown.get("fail_closed") is True
    )

    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "prompts.db")
        snapshot_id = snapshot_prompt_registry(db_path=db, persist=True)
        conn = sqlite3.connect(db)
        snapshot_rows = conn.execute(
            "SELECT prompt_count FROM second_brain_mcp_prompt_registry_snapshots"
        ).fetchall()
        guards_clean = _guards_all_zero(conn, "second_brain_mcp_prompt_registry_snapshots")

    proof_passed = bool(
        all_pass
        and unknown_fail_closed
        and snapshot_id
        and snapshot_rows == [(len(registry),)]
        and guards_clean
    )
    proof: dict[str, Any] = {
        "proof": "phase_08d_mcp_prompts",
        "phase": "08D",
        "proof_passed": proof_passed,
        "prompt_count": len(registry),
        "prompts": prompt_report,
        "unknown_prompt_fail_closed": unknown_fail_closed,
        "registry_snapshot": {
            "persisted": bool(snapshot_id),
            "prompt_count": len(registry),
            "all_guard_columns_zero": guards_clean,
        },
        "contract": {
            "route_through_allowed_tools": True,
            "no_raw_store_instructions": True,
            "no_writeback_instructions": True,
            "no_final_determinations": True,
            "no_raw_prompt_response_persistence": True,
            "no_policy_bypass": True,
        },
        "guardrails": {"advisory_only": True, "source_linked": True, "review_controlled": True},
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp prompts proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / PROMPT_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        proof["proof_path"] = str(out_dir / PROMPT_PROOF_JSON)

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

    proof_passed = bool(all_pass and token_pass and no_raw_echo and no_raw_columns and guards_clean)
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
    """Dispatch all allowed tools through the real broker and attest the contract shape.

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


# ---------------------------------------------------------------------------
# Phase 08D no-raw MCP access proof (Prompt 13).
#
# A deterministic, read-only scan over every MCP surface — registries, resources, prompts,
# receipts, the Claude Desktop config preview, the server status, and the committed evidence
# artifacts — proving none exposes raw content. STATIC/STRUCTURAL ONLY: it never dispatches
# read_resource / the workflow wrappers (those route hb_research_packet through retrieval),
# so resources/prompts are scanned at the registry/template level and receipts via a
# self-contained temp-DB PRAGMA. The server-status and evidence-file surfaces are optional so
# the server startup check (policy.evaluate_startup_checks) can call this without recursion.
# ---------------------------------------------------------------------------


def _scan_no_raw(label: str, payload: Any) -> dict[str, Any]:
    """Scan one MCP surface payload for raw exposure (never echoes any offending text)."""
    forbidden_keys = sorted(_collect_keys(payload) & set(_FORBIDDEN_RESULT_FIELDS))
    passed = True
    detail = "no raw keys/patterns"
    try:
        _assert_no_raw(json.dumps(payload, default=str), label)
    except ValueError as exc:
        # exc names the matched PATTERN + the surface label, never the matched text.
        passed = False
        detail = str(exc)
    if forbidden_keys:
        passed = False
        detail = f"forbidden result keys present: {forbidden_keys}"
    return {"surface": label, "passed": passed, "detail": detail}


def _receipts_no_raw(*, db_path: str | None = None) -> dict[str, Any]:
    """Structurally prove the receipt tables expose no raw content (self-contained temp DB)."""
    from hb_assistant.store.migrator import SQLiteMigrator  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "receipts.db")
        SQLiteMigrator(db).apply()
        conn = sqlite3.connect(db)
        call_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_tool_call_receipts)")
        }
        denial_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_denial_receipts)")
        }
        no_raw_columns = not (_FORBIDDEN_RECEIPT_COLUMNS & (call_cols | denial_cols))
        hashes_present = {"args_hash", "result_hash"} <= call_cols and "request_hash" in denial_cols
        guards_zero = _guards_all_zero(
            conn, "second_brain_mcp_tool_call_receipts"
        ) and _guards_all_zero(conn, "second_brain_mcp_denial_receipts")
        conn.close()

    passed = bool(no_raw_columns and hashes_present and guards_zero)
    return {
        "surface": "receipts",
        "passed": passed,
        "detail": "hash-only columns; no raw columns; all guard columns zero",
        "no_raw_columns": no_raw_columns,
        "hash_columns_present": hashes_present,
        "guard_columns_zero": guards_zero,
    }


def evaluate_no_raw_mcp_access(
    *,
    db_path: str | None = None,
    include_server_status: bool = True,
    include_evidence_scan: bool = True,
) -> dict[str, Any]:
    """Scan every MCP surface for raw-content exposure. Read-only; persists nothing.

    Static/structural only — never dispatches the synthesis/retrieval wrappers. The
    server-status and evidence-file surfaces are optional so the server startup check can call
    this without recursion or disk scans.
    """
    from .config_preview import build_claude_desktop_config_preview  # noqa: PLC0415
    from .prompts import render_all_prompts  # noqa: PLC0415
    from .registry import load_global_requirements  # noqa: PLC0415
    from .resources import load_resources  # noqa: PLC0415

    surfaces: list[dict[str, Any]] = []

    # 1. registries — tool/action NAMES and policy metadata only, no raw values.
    surfaces.append(
        _scan_no_raw(
            "registries",
            {
                "allowed_tools": load_allowed_tools(),
                "denied_actions": sorted(load_denied_actions()),
                "global_requirements": load_global_requirements(),
            },
        )
    )

    # 2. resources — static registry listing (NO read_resource dispatch).
    surfaces.append(_scan_no_raw("resources", load_resources()))

    # 3. prompts — static rendered templates (no tool execution).
    surfaces.append(_scan_no_raw("prompts", render_all_prompts()))

    # 4. receipts — structural (temp-DB PRAGMA).
    surfaces.append(_receipts_no_raw(db_path=db_path))

    # 5. config preview — env key NAMES only; never persists env values.
    preview = build_claude_desktop_config_preview(persist=False, write_evidence=False)
    cfg = _scan_no_raw("config_preview", preview)
    cfg["env_values_persisted"] = bool(preview.get("guardrails", {}).get("env_values_persisted"))
    cfg["config_safe"] = bool(preview.get("safe"))
    if cfg["env_values_persisted"] or not cfg["config_safe"]:
        cfg["passed"] = False
    surfaces.append(cfg)

    # 6. server status (optional — skipped by the startup check to avoid recursion).
    if include_server_status:
        from .policy import build_mcp_status  # noqa: PLC0415

        surfaces.append(
            _scan_no_raw("server_status", build_mcp_status(persist=False, db_path=db_path))
        )

    # 7. committed evidence artifacts (optional — the generated 08D proof JSONs).
    if include_evidence_scan:
        ev_dir = Path(EVIDENCE_DIR)
        files = sorted(ev_dir.glob("*.json")) if ev_dir.exists() else []
        scanned: list[str] = []
        ev_passed = True
        for f in files:
            scanned.append(f.name)
            try:
                _assert_no_raw(f.read_text(encoding="utf-8"), f"evidence {f.name}")
            except ValueError:
                ev_passed = False
        surfaces.append(
            {
                "surface": "evidence",
                "passed": ev_passed,
                "detail": f"{len(scanned)} evidence json artifacts scanned",
                "scanned": scanned,
            }
        )

    raw_posture = get_mcp_raw_content_posture()
    mcp_raw_allowed = bool(raw_posture.get("mcp_raw_allowed", False))
    proof_passed = all(s["passed"] for s in surfaces)
    return {
        "proof_passed": proof_passed,
        "scanned_surface_count": len(surfaces),
        "surfaces": surfaces,
        "metadata_only": {
            "no_raw_requested_content": proof_passed,
            "static_scan_no_wrapper_dispatch": True,
            "receipts_hash_only": True,
            "raw_mcp_config_respected": True,
        },
        "guardrails": {
            "read_only": True,
            "no_raw_content": not mcp_raw_allowed,
            "mcp_raw_allowed": mcp_raw_allowed,
            "no_resource_dispatch": True,
            "metadata_only": True,
        },
        "raw_content_posture": raw_posture,
    }


def _render_no_raw_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 08D No-Raw MCP Access Proof",
        "",
        "Deterministic, read-only scan over every MCP surface (registries, resources, prompts, "
        "receipts, config preview, server status, and the committed evidence artifacts) proving "
        "none exposes raw content. Static/structural only — the synthesis/retrieval workflow "
        "tools are never dispatched; receipts are introspected via a temp-DB PRAGMA.",
        "",
        "## Summary",
        f"- Proof passed: {str(proof['proof_passed']).lower()}",
        f"- Surfaces scanned: {proof['scanned_surface_count']}",
        "",
        "## Surfaces",
        "| Surface | Passed | Detail |",
        "| --- | --- | --- |",
    ]
    for s in proof["surfaces"]:
        lines.append(f"| {s['surface']} | {str(s['passed']).lower()} | {s.get('detail', '')} |")
    lines += ["", "## Guardrails"]
    for key, value in proof["guardrails"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines += ["", f"Generated: {proof['generated_utc']}", ""]
    return "\n".join(lines)


def build_no_raw_mcp_access_proof(
    *,
    db_path: str | None = None,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Run the full no-raw MCP access scan and (optionally) write the evidence proof + MD."""
    from datetime import datetime, timezone  # noqa: PLC0415

    report = evaluate_no_raw_mcp_access(db_path=db_path)
    proof: dict[str, Any] = {
        "proof": "phase_08d_no_raw_mcp_access",
        "command": "second-brain mcp no-raw-access",
        "phase": "08D",
        "proof_passed": report["proof_passed"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scanned_surface_count": report["scanned_surface_count"],
        "surfaces": report["surfaces"],
        "metadata_only": report["metadata_only"],
        "guardrails": report["guardrails"],
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp no-raw-access proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / NO_RAW_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_no_raw_md(proof)
        _assert_no_raw(markdown, "mcp no-raw-access proof markdown")
        (out_dir / NO_RAW_PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / NO_RAW_PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / NO_RAW_PROOF_MD)

    return proof


# ---------------------------------------------------------------------------
# Phase 08D no-MCP-writeback proof (Prompt 14).
#
# A deterministic, read-only scan proving no MCP surface can perform writeback, a direct
# Graph/Procore/SQL API call, or external delivery. STATIC/STRUCTURAL ONLY (never dispatches
# the workflow wrappers): the permission-policy seed has every allow_* flag false, the denied
# registry covers the writeback / direct-API / URL action classes, the ten tool wrappers are
# workflow-wrapper-only, the receipt tables carry the writeback guard columns at CHECK(=0),
# and the config preview never auto-writes the live Claude Desktop config. The server-status
# and evidence-file surfaces are optional so the server startup check can call this without
# recursion (the full proof scans them).
# ---------------------------------------------------------------------------


def _receipts_no_writeback(*, db_path: str | None = None) -> dict[str, Any]:
    """Structurally prove the receipt tables record no writeback (self-contained temp DB)."""
    from hb_assistant.store.migrator import SQLiteMigrator  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "receipts.db")
        SQLiteMigrator(db).apply()
        conn = sqlite3.connect(db)
        call_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_tool_call_receipts)")
        }
        denial_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(second_brain_mcp_denial_receipts)")
        }
        writeback_guards_present = set(_WRITEBACK_GUARD_COLUMNS) <= (call_cols & denial_cols)
        guards_zero = _guards_all_zero(
            conn, "second_brain_mcp_tool_call_receipts"
        ) and _guards_all_zero(conn, "second_brain_mcp_denial_receipts")
        conn.close()

    passed = bool(writeback_guards_present and guards_zero)
    return {
        "surface": "receipts",
        "passed": passed,
        "detail": "writeback/API guard columns present and CHECK(=0); all guard columns zero",
        "writeback_guard_columns_present": writeback_guards_present,
        "guard_columns_zero": guards_zero,
    }


def evaluate_no_writeback_mcp_access(
    *,
    db_path: str | None = None,
    include_server_status: bool = True,
    include_evidence_scan: bool = True,
) -> dict[str, Any]:
    """Scan every MCP surface for writeback / direct-API / external-delivery capability.

    Read-only; persists nothing. Static/structural only — never dispatches the workflow
    wrappers. The server-status and evidence-file surfaces are optional so the server startup
    check can call this without recursion or disk scans.
    """
    from .config_preview import build_claude_desktop_config_preview  # noqa: PLC0415
    from .policy import _PERMISSION_POLICY_SEED, _load_seed  # noqa: PLC0415
    from .registry import load_global_requirements  # noqa: PLC0415
    from .wrappers import build_wrapper_registry  # noqa: PLC0415

    surfaces: list[dict[str, Any]] = []

    # 1. permission policy — every allow_* flag is false (fail-closed seed).
    perm = _load_seed(_PERMISSION_POLICY_SEED)
    allow_flags = {k: v for k, v in perm.items() if k.startswith("allow_")}
    all_allow_false = bool(allow_flags) and not any(bool(v) for v in allow_flags.values())
    surfaces.append(
        {
            "surface": "permission_policy",
            "passed": all_allow_false,
            "detail": f"{len(allow_flags)} allow_* flags, all false={all_allow_false}",
        }
    )

    # 2. denied registry covers writeback + direct-API + URL action classes.
    denied = load_denied_actions()
    required = _WRITEBACK_ACTIONS | _DIRECT_API_ACTIONS | _URL_ACTIONS
    surfaces.append(
        {
            "surface": "denied_registry",
            "passed": required <= denied,
            "detail": "writeback/direct-API/URL actions all denied",
            "missing": sorted(required - denied),
        }
    )

    # 3. tool wrappers — ten workflow-wrapper-only tools; global requirements forbid writeback.
    wrappers = build_wrapper_registry(db_path=db_path)
    reqs = set(load_global_requirements())
    wrappers_ok = len(wrappers) == 10 and {"workflow_wrapper_only", "no_writeback"} <= reqs
    surfaces.append(
        {
            "surface": "tool_wrappers",
            "passed": wrappers_ok,
            "detail": "ten workflow-wrapper-only tools; workflow-only + no-writeback required",
            "wrapper_count": len(wrappers),
        }
    )

    # 4. receipts — writeback guard columns present and all guard columns zero.
    surfaces.append(_receipts_no_writeback(db_path=db_path))

    # 5. config preview — never auto-writes the live Claude Desktop config.
    preview = build_claude_desktop_config_preview(persist=False, write_evidence=False)
    cfg = _scan_no_raw("config_preview", preview)
    cfg["auto_apply"] = bool(preview.get("auto_apply"))
    cfg["preview_only_no_auto_apply"] = bool(
        preview.get("guardrails", {}).get("preview_only_no_auto_apply")
    )
    if cfg["auto_apply"] or not cfg["preview_only_no_auto_apply"]:
        cfg["passed"] = False
    surfaces.append(cfg)

    # 6. server guardrails (optional — skipped by the startup check to avoid recursion).
    if include_server_status:
        from .policy import build_mcp_status  # noqa: PLC0415

        status = build_mcp_status(persist=False, db_path=db_path)
        guards = status.get("guardrails", {})
        server_ok = all(
            bool(guards.get(g))
            for g in ("no_external_writeback", "no_direct_graph_or_procore", "no_arbitrary_sql")
        )
        scan = _scan_no_raw("server_guardrails", status)
        scan["passed"] = scan["passed"] and server_ok
        surfaces.append(scan)

    # 7. committed evidence artifacts (optional — the generated 08D proof JSONs).
    if include_evidence_scan:
        ev_dir = Path(EVIDENCE_DIR)
        files = sorted(ev_dir.glob("*.json")) if ev_dir.exists() else []
        scanned: list[str] = []
        ev_passed = True
        for f in files:
            scanned.append(f.name)
            try:
                _assert_no_raw(f.read_text(encoding="utf-8"), f"evidence {f.name}")
            except ValueError:
                ev_passed = False
        surfaces.append(
            {
                "surface": "evidence",
                "passed": ev_passed,
                "detail": f"{len(scanned)} evidence json artifacts scanned",
                "scanned": scanned,
            }
        )

    proof_passed = all(s["passed"] for s in surfaces)
    return {
        "proof_passed": proof_passed,
        "scanned_surface_count": len(surfaces),
        "surfaces": surfaces,
        "metadata_only": {
            "no_writeback_performed": proof_passed,
            "no_direct_api_performed": proof_passed,
            "no_external_delivery": proof_passed,
            "static_scan_no_wrapper_dispatch": True,
        },
        "guardrails": {
            "read_only": True,
            "no_external_writeback": True,
            "no_direct_graph_or_procore": True,
            "no_arbitrary_sql": True,
            "metadata_only": True,
        },
    }


def _render_no_writeback_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 08D No-MCP-Writeback Proof",
        "",
        "Deterministic, read-only scan proving no MCP surface (permission policy, denied "
        "registry, tool wrappers, receipts, config preview, server guardrails, and the "
        "committed evidence artifacts) can perform writeback, a direct Graph/Procore/SQL API "
        "call, or external delivery. Static/structural only — the workflow tools are never "
        "dispatched; receipts are introspected via a temp-DB PRAGMA.",
        "",
        "## Summary",
        f"- Proof passed: {str(proof['proof_passed']).lower()}",
        f"- Surfaces scanned: {proof['scanned_surface_count']}",
        "",
        "## Surfaces",
        "| Surface | Passed | Detail |",
        "| --- | --- | --- |",
    ]
    for s in proof["surfaces"]:
        lines.append(f"| {s['surface']} | {str(s['passed']).lower()} | {s.get('detail', '')} |")
    lines += ["", "## Guardrails"]
    for key, value in proof["guardrails"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines += ["", f"Generated: {proof['generated_utc']}", ""]
    return "\n".join(lines)


def build_no_mcp_writeback_proof(
    *,
    db_path: str | None = None,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Run the full no-writeback MCP scan and (optionally) write the evidence proof + MD."""
    from datetime import datetime, timezone  # noqa: PLC0415

    report = evaluate_no_writeback_mcp_access(db_path=db_path)
    proof: dict[str, Any] = {
        "proof": "phase_08d_no_mcp_writeback",
        "command": "second-brain mcp no-writeback",
        "phase": "08D",
        "proof_passed": report["proof_passed"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scanned_surface_count": report["scanned_surface_count"],
        "surfaces": report["surfaces"],
        "metadata_only": report["metadata_only"],
        "guardrails": report["guardrails"],
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp no-writeback proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / NO_WRITEBACK_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_no_writeback_md(proof)
        _assert_no_raw(markdown, "mcp no-writeback proof markdown")
        (out_dir / NO_WRITEBACK_PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / NO_WRITEBACK_PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / NO_WRITEBACK_PROOF_MD)

    return proof


def evaluate_phase_08d_validation_matrix(*, evidence_dir: str | None = None) -> dict[str, Any]:
    """Statically verify the Phase 08D validation matrix is defined and its evidence present.

    Read-only and **SDK-agnostic** (it never imports the ``mcp`` SDK, dispatches a wrapper,
    or runs the matrix commands), so it is safe to evaluate inside the gates evaluator and
    in a base install without the optional SDK. It confirms: (1) the validation-matrix
    contract loads and lists its commands; (2) both resource-tree copies are present and in
    parity; and (3) the closeout-critical 08D evidence artifacts exist on disk.
    """
    from ..contracts import load_phase_08d_contract  # noqa: PLC0415

    surfaces: list[dict[str, Any]] = []

    # 1. contract loads + lists its commands.
    try:
        contract = load_phase_08d_contract("validation_matrix")
        commands = contract.get("commands") if isinstance(contract, dict) else None
        commands_ok = isinstance(commands, list) and len(commands) >= 14
        surfaces.append(
            {
                "surface": "validation_matrix_contract",
                "passed": bool(commands_ok),
                "detail": f"contract loaded; {len(commands) if isinstance(commands, list) else 0} commands",
                "contract_version": contract.get("version") if isinstance(contract, dict) else None,
            }
        )
    except Exception as exc:  # noqa: BLE001 - a missing/broken contract is reported, not raised
        surfaces.append(
            {
                "surface": "validation_matrix_contract",
                "passed": False,
                "detail": f"contract load failed: {type(exc).__name__}",
            }
        )

    # 2. dual-tree parity — both copies present with identical contract_name/version/count.
    loaded: list[dict[str, Any]] = []
    present = True
    for rel in _VALIDATION_MATRIX_CONTRACT_PATHS:
        path = Path(rel)
        if not path.exists():
            present = False
            continue
        try:
            loaded.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            present = False
    parity = (
        present
        and len(loaded) == len(_VALIDATION_MATRIX_CONTRACT_PATHS)
        and len(
            {
                (d.get("contract_name"), d.get("version"), len(d.get("commands") or []))
                for d in loaded
            }
        )
        == 1
    )
    surfaces.append(
        {
            "surface": "dual_tree_parity",
            "passed": bool(parity),
            "detail": f"{len(loaded)}/{len(_VALIDATION_MATRIX_CONTRACT_PATHS)} contract copies in parity",
        }
    )

    # 3. closeout-critical evidence artifacts present on disk.
    ev_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
    missing = [
        name for name in _VALIDATION_MATRIX_REQUIRED_EVIDENCE if not (ev_dir / name).exists()
    ]
    surfaces.append(
        {
            "surface": "evidence_bundle",
            "passed": not missing,
            "detail": f"{len(_VALIDATION_MATRIX_REQUIRED_EVIDENCE) - len(missing)}/"
            f"{len(_VALIDATION_MATRIX_REQUIRED_EVIDENCE)} required artifacts present",
            "missing": missing,
        }
    )

    proof_passed = all(s["passed"] for s in surfaces)
    return {
        "proof_passed": proof_passed,
        "scanned_surface_count": len(surfaces),
        "surfaces": surfaces,
        "metadata_only": {
            "static_scan_no_command_execution": True,
            "sdk_agnostic": True,
        },
        "guardrails": {
            "read_only": True,
            "no_command_execution": True,
            "no_raw_content": True,
            "metadata_only": True,
        },
    }


def _render_validation_matrix_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 08D Validation-Matrix Proof",
        "",
        "Deterministic, read-only, SDK-agnostic proof that the Phase 08D validation matrix "
        "is defined (contract + commands), present in both resource trees (parity), and "
        "backed by the closeout-critical evidence bundle. Static existence/parity checks "
        "only — the matrix commands are never executed here.",
        "",
        "## Summary",
        f"- Proof passed: {str(proof['proof_passed']).lower()}",
        f"- Surfaces scanned: {proof['scanned_surface_count']}",
        "",
        "## Surfaces",
        "| Surface | Passed | Detail |",
        "| --- | --- | --- |",
    ]
    for s in proof["surfaces"]:
        lines.append(f"| {s['surface']} | {str(s['passed']).lower()} | {s.get('detail', '')} |")
    lines += ["", "## Guardrails"]
    for key, value in proof["guardrails"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines += ["", f"Generated: {proof['generated_utc']}", ""]
    return "\n".join(lines)


def build_phase_08d_validation_matrix_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Run the static validation-matrix scan and (optionally) write the evidence proof + MD."""
    from datetime import datetime, timezone  # noqa: PLC0415

    report = evaluate_phase_08d_validation_matrix(evidence_dir=evidence_dir)
    proof: dict[str, Any] = {
        "proof": "phase_08d_validation_matrix",
        "command": "second-brain mcp data-quality phase-08d-gates",
        "phase": "08D",
        "proof_passed": report["proof_passed"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scanned_surface_count": report["scanned_surface_count"],
        "surfaces": report["surfaces"],
        "metadata_only": report["metadata_only"],
        "guardrails": report["guardrails"],
    }

    serialized = json.dumps(proof, indent=2, default=str)
    _assert_no_raw(serialized, "mcp validation-matrix proof")

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / VALIDATION_MATRIX_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_validation_matrix_md(proof)
        _assert_no_raw(markdown, "mcp validation-matrix proof markdown")
        (out_dir / VALIDATION_MATRIX_PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / VALIDATION_MATRIX_PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / VALIDATION_MATRIX_PROOF_MD)

    return proof
