"""Phase 08D MCP server startup policy + status (Prompt 03).

Deterministic, read-only evaluation of the fail-closed startup conditions for the local
stdio MCP server: schema version, server-policy seed, the four registry contracts, the
fail-closed permission policy, and stdio-only transport. Both MCP-specific guard proofs are
now wired and evaluated live: ``no_raw_access_proof`` (Prompt 13) and ``no_writeback_proof``
(Prompt 14). When every check passes and the optional MCP SDK is installed,
``ready_to_serve`` is true and the local stdio server serves (Prompt 15, via
:mod:`.server` / :mod:`.sdk_server`); a missing SDK (``mcp_sdk_not_installed``) keeps
serving fail-closed. Nothing in *this* module opens a socket, imports the MCP SDK, or
persists raw content — it only evaluates read-only status.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from ..contracts import load_phase_08d_contract
from .registry import load_allowed_tools, load_denied_actions
from .store import _sha256, write_mcp_server_config_snapshot

TRANSPORT = "stdio"
_DENIED_TRANSPORTS = ("http", "sse", "websocket", "tcp", "remote")
_SERVER_POLICY_SEED = "resources/config/phase_08d_mcp_server_policy.seed.yaml"
_PERMISSION_POLICY_SEED = "resources/config/phase_08d_mcp_permission_policy.seed.yaml"

# Both MCP guard proofs are now wired and evaluated live in evaluate_startup_checks
# (no-raw-access: Prompt 13; no-writeback: Prompt 14), so no guard proof is a deferred serve
# blocker. The optional MCP SDK is the only remaining serve gate (appended in build_mcp_status).
_DEFERRED_SERVE_BLOCKERS: tuple[str, ...] = ()
_MCP_GUARDRAILS = {
    "local_first": True,
    "transport_stdio_only": True,
    "no_network_from_mcp_layer": True,
    "fail_closed_startup": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "no_direct_graph_or_procore": True,
    "no_arbitrary_sql": True,
    "no_final_determination": True,
    "mcp_tools_exposed": False,
}


def _load_seed(rel_path: str) -> dict[str, Any]:
    """Load a repo-rooted ``.seed.yaml`` policy (read-only)."""
    path = Path(rel_path)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _policy_version() -> str:
    seed = _load_seed(_SERVER_POLICY_SEED)
    version = seed.get("policy_version")
    if isinstance(version, str):
        return version
    contract = load_phase_08d_contract("server_config_contract")
    version = contract.get("version")
    return version if isinstance(version, str) else "unknown"


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _registry_present(name: str, logical: str) -> dict[str, str]:
    try:
        contract = load_phase_08d_contract(logical)
    except Exception as exc:  # noqa: BLE001 - any load failure is a fail-closed condition
        return _check(name, "fail", f"contract load failed: {exc!r}")
    if not contract or not contract.get("contract_name"):
        return _check(name, "fail", "contract missing or empty")
    return _check(name, "pass", f"loaded {contract.get('contract_name')}")


def evaluate_startup_checks(*, db_path: str | None = None) -> dict[str, Any]:
    """Evaluate the fail-closed startup checks. Read-only; persists nothing.

    ``foundation_ok`` is True iff no check is ``fail``. Both guard-proof checks are evaluated
    live: ``no_raw_access_proof`` (Prompt 13) and ``no_writeback_proof`` (Prompt 14).
    """
    checks: list[dict[str, str]] = []

    # 1. schema version
    if LATEST_SCHEMA_VERSION >= 37:
        checks.append(_check("schema_version_v37", "pass", f"schema={LATEST_SCHEMA_VERSION}"))
    else:
        checks.append(
            _check("schema_version_v37", "fail", f"schema={LATEST_SCHEMA_VERSION} < 37 (stale)")
        )

    # 2. server policy seed loaded + stdio-only
    server_seed = _load_seed(_SERVER_POLICY_SEED)
    transport = server_seed.get("transport") if isinstance(server_seed, dict) else None
    allowed = transport.get("allowed") if isinstance(transport, dict) else None
    if server_seed and allowed == [TRANSPORT]:
        checks.append(_check("server_policy_seed_loaded", "pass", "transport.allowed=[stdio]"))
    else:
        checks.append(
            _check("server_policy_seed_loaded", "fail", "missing seed or transport not stdio-only")
        )

    # 3-6. registries present (the four 08D contracts)
    checks.append(_registry_present("allowed_tools_registry_present", "allowed_tools_contract"))
    checks.append(_registry_present("denied_tools_registry_present", "denied_tools_contract"))
    checks.append(_registry_present("resource_registry_present", "resources_contract"))
    checks.append(_registry_present("prompt_registry_present", "prompts_contract"))

    # 7. permission policy fail-closed (every allow_* is false)
    perm = _load_seed(_PERMISSION_POLICY_SEED)
    allow_flags = {k: v for k, v in perm.items() if k.startswith("allow_")}
    if allow_flags and not any(bool(v) for v in allow_flags.values()):
        checks.append(
            _check("permission_policy_fail_closed", "pass", f"{len(allow_flags)} allow_* all false")
        )
    else:
        checks.append(
            _check("permission_policy_fail_closed", "fail", "missing seed or an allow_* is true")
        )

    # 8. transport stdio-only (denied list covers all network transports)
    denied = transport.get("denied") if isinstance(transport, dict) else None
    if isinstance(denied, list) and all(t in denied for t in _DENIED_TRANSPORTS):
        checks.append(
            _check("transport_stdio_only", "pass", "http/sse/websocket/tcp/remote denied")
        )
    else:
        checks.append(_check("transport_stdio_only", "fail", "network transports not all denied"))

    # 9. MCP no-raw-access guard proof (Prompt 13) — evaluated live, non-recursively
    # (server-status + evidence-file surfaces are excluded here; the full proof scans them).
    try:
        from .proof import evaluate_no_raw_mcp_access  # noqa: PLC0415 - avoid import cycle

        nra = evaluate_no_raw_mcp_access(
            db_path=db_path, include_server_status=False, include_evidence_scan=False
        )
        if nra["proof_passed"]:
            checks.append(_check("no_raw_access_proof", "pass", "MCP no-raw-access proof passes"))
        else:
            failed = [s["surface"] for s in nra["surfaces"] if not s["passed"]]
            checks.append(_check("no_raw_access_proof", "fail", f"no-raw scan failed: {failed}"))
    except Exception as exc:  # noqa: BLE001 - any scan failure is fail-closed
        checks.append(_check("no_raw_access_proof", "fail", f"no-raw scan errored: {exc!r}"))

    # 10. MCP no-writeback guard proof (Prompt 14) — evaluated live, non-recursively.
    try:
        from .proof import evaluate_no_writeback_mcp_access  # noqa: PLC0415 - avoid import cycle

        nwb = evaluate_no_writeback_mcp_access(
            db_path=db_path, include_server_status=False, include_evidence_scan=False
        )
        if nwb["proof_passed"]:
            checks.append(_check("no_writeback_proof", "pass", "MCP no-writeback proof passes"))
        else:
            failed = [s["surface"] for s in nwb["surfaces"] if not s["passed"]]
            checks.append(
                _check("no_writeback_proof", "fail", f"no-writeback scan failed: {failed}")
            )
    except Exception as exc:  # noqa: BLE001 - any scan failure is fail-closed
        checks.append(_check("no_writeback_proof", "fail", f"no-writeback scan errored: {exc!r}"))

    foundation_ok = not any(c["status"] == "fail" for c in checks)
    deferred = [c["name"] for c in checks if c["status"] == "deferred"]
    return {
        "checks": checks,
        "foundation_ok": foundation_ok,
        "deferred": deferred,
    }


def build_mcp_status(*, db_path: str | None = None, persist: bool = True) -> dict[str, Any]:
    """Build the MCP server-foundation status posture (metadata-only).

    Reports the startup checks, SDK availability, and why the server is not yet
    ``ready_to_serve``. When ``persist`` is True a metadata-only
    ``second_brain_mcp_server_config_snapshots`` row is written.
    """
    startup = evaluate_startup_checks(db_path=db_path)
    mcp_sdk_available = importlib.util.find_spec("mcp") is not None

    # The broker (Prompt 04) and the ten workflow wrappers (Prompt 05 + Phase 09 packet) are wired; the
    # Prompt 13/14 guard proofs pass, so serving over stdio is gated only on the optional
    # MCP SDK being installed (``ready_to_serve`` below).
    from .prompts import load_prompts  # noqa: PLC0415 - avoid import cycle at module load
    from .resources import load_resources  # noqa: PLC0415 - avoid import cycle at module load
    from .wrappers import (
        build_wrapper_registry,  # noqa: PLC0415 - avoid import cycle at module load
    )

    try:
        allowed_tool_specs = len(load_allowed_tools())
        denied_actions = len(load_denied_actions())
        tools_registered = len(build_wrapper_registry())
        resources_count = len(load_resources())
        prompts_count = len(load_prompts())
    except Exception:  # noqa: BLE001 - a missing registry is reported, not raised, by status
        allowed_tool_specs = 0
        denied_actions = 0
        tools_registered = 0
        resources_count = 0
        prompts_count = 0

    serve_blockers: list[str] = list(_DEFERRED_SERVE_BLOCKERS)
    if not mcp_sdk_available:
        serve_blockers.append("mcp_sdk_not_installed")
    ready_to_serve = startup["foundation_ok"] and not serve_blockers

    policy_version = _policy_version()
    posture = {
        "transport": TRANSPORT,
        "schema_version": LATEST_SCHEMA_VERSION,
        "foundation_ok": startup["foundation_ok"],
        "mcp_sdk_available": mcp_sdk_available,
        "mcp_tools_registered": tools_registered,
        "mcp_allowed_tool_specs": allowed_tool_specs,
        "mcp_denied_actions": denied_actions,
        "serve_blockers": serve_blockers,
        "checks": startup["checks"],
    }
    config_hash = _sha256(posture)

    snapshot_id: str | None = None
    if persist:
        snapshot_id = write_mcp_server_config_snapshot(
            transport=TRANSPORT,
            config_hash=config_hash,
            policy_version=policy_version,
            db_path=db_path,
        )

    return {
        "command": "second-brain mcp status",
        "phase": "08D",
        "transport": TRANSPORT,
        "schema_version": LATEST_SCHEMA_VERSION,
        "policy_version": policy_version,
        "foundation_ok": startup["foundation_ok"],
        "ready_to_serve": ready_to_serve,
        "mcp_sdk_available": mcp_sdk_available,
        "mcp_tools_registered": tools_registered,
        "mcp_allowed_tool_specs": allowed_tool_specs,
        "mcp_denied_actions": denied_actions,
        "mcp_resources": resources_count,
        "mcp_prompts": prompts_count,
        "checks": startup["checks"],
        "deferred": startup["deferred"],
        "serve_blockers": serve_blockers,
        "config_hash": config_hash,
        "snapshot_id": snapshot_id,
        "guardrails": dict(_MCP_GUARDRAILS),
    }
