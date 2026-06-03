"""Phase 08D MCP allowed/denied registry loaders (Prompt 04).

Loads the policy-gated registries the tool broker enforces: the nine allowed workflow
tools (name → wrapper/maps_to/risk/receipt_required), the explicit denied-action set, and
the global requirements. Fail-closed: a missing or empty registry raises so the broker
never dispatches against an unknown policy surface.
"""

from __future__ import annotations

from typing import Any

from ..contracts import load_phase_08d_contract


class RegistryUnavailable(RuntimeError):
    """Raised when a required MCP registry is missing or empty (fail-closed)."""


def load_allowed_tools() -> dict[str, dict[str, Any]]:
    """Return ``{tool_name: spec}`` for the nine allowed workflow tools."""
    contract = load_phase_08d_contract("allowed_tools_contract")
    tools = contract.get("tools") if isinstance(contract, dict) else None
    if not isinstance(tools, list) or not tools:
        raise RegistryUnavailable("allowed_tools registry missing or empty")
    registry: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if not isinstance(tool, dict) or not tool.get("name") or not tool.get("wrapper"):
            raise RegistryUnavailable(f"malformed allowed tool entry: {tool!r}")
        registry[str(tool["name"])] = {
            "wrapper": str(tool["wrapper"]),
            "maps_to": tool.get("maps_to"),
            "risk": tool.get("risk"),
            "receipt_required": bool(tool.get("receipt_required", True)),
        }
    return registry


def load_denied_actions() -> set[str]:
    """Return the explicit set of denied action names."""
    contract = load_phase_08d_contract("denied_tools_contract")
    actions = contract.get("denied_actions") if isinstance(contract, dict) else None
    if not isinstance(actions, list) or not actions:
        raise RegistryUnavailable("denied_actions registry missing or empty")
    return {str(a) for a in actions}


def load_global_requirements() -> list[str]:
    """Return the allowed-tools global requirements (e.g. workflow_wrapper_only)."""
    contract = load_phase_08d_contract("allowed_tools_contract")
    reqs = contract.get("global_requirements") if isinstance(contract, dict) else None
    return [str(r) for r in reqs] if isinstance(reqs, list) else []
