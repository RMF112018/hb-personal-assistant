"""Phase 08D policy-gated MCP tool broker (Prompt 04).

Every MCP tool call passes through ``ToolBroker.dispatch``: canonicalize → **deny first**
→ allowed-registry check → argument validation → workflow-wrapper invocation → bounded,
no-raw output validation → metadata-only receipt. It fails closed on every error path and
never persists or returns raw arguments, results, prompts, responses, SQL, tokens, URLs,
or determinations.

The workflow wrappers are implemented in Prompt 05 (+ Phase 09 daily-brief packet); the broker dispatches through an
injectable ``wrappers`` registry. With no wrapper wired an allowed tool fails closed with
``wrapper_unavailable`` — the broker never stubs or fabricates a result.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from ..financial_review_routing import _assert_no_raw
from .policy import _policy_version
from .registry import load_allowed_tools, load_denied_actions

# Phase 10A P09: raw MCP gating (default disabled)
try:
    from ..local_ai.contracts import load_raw_content_policy
except Exception:  # pragma: no cover
    load_raw_content_policy = None  # type: ignore
from .store import (
    _sha256,
    write_mcp_denial_receipt,
    write_mcp_tool_call_receipt,
)

Wrapper = Callable[[dict[str, Any]], dict[str, Any]]

MAX_RESULTS = 50
_MAX_ARGS_BYTES = 16 * 1024

# Fail-closed denial reason codes.
REASON_ACTION_DENIED = "action_denied_by_policy"
REASON_TOOL_NOT_ALLOWED = "tool_not_allowed"
REASON_WRAPPER_UNAVAILABLE = "wrapper_unavailable"
REASON_INVALID_ARGUMENTS = "invalid_arguments"
REASON_UNSAFE_OUTPUT = "unsafe_output"
REASON_BROKER_ERROR = "broker_error"

DENIAL_REASONS = (
    REASON_ACTION_DENIED,
    REASON_TOOL_NOT_ALLOWED,
    REASON_WRAPPER_UNAVAILABLE,
    REASON_INVALID_ARGUMENTS,
    REASON_UNSAFE_OUTPUT,
    REASON_BROKER_ERROR,
)

_POLICY_POSTURE = {
    "advisory_only": True,
    "local_only": True,
    "no_writeback": True,
    "no_raw": True,
    "no_final_determination": True,
}


def _compute_mcp_raw_allowed() -> bool:
    """Return True only when raw content downstream is explicitly enabled for MCP under a permissive mode."""
    try:
        if load_raw_content_policy is None:
            return False
        rc = load_raw_content_policy()
        rcd = getattr(rc, "raw_content", None)
        downstream = getattr(rcd, "downstream", None) if rcd is not None else None
        flag = (
            bool(getattr(downstream, "mcp_allow_raw_content", False))
            if downstream is not None
            else False
        )
        mode = str(getattr(rcd, "mode", "") or "").strip().lower() if rcd is not None else ""
        permissive = (
            mode in ("", "all_supported", "all_supported_plus_downstream") or "downstream" in mode
        )
        return bool(flag and permissive)
    except Exception:
        return False


class ToolBroker:
    """Policy-gated dispatch broker over the allowed/denied registries."""

    def __init__(
        self,
        *,
        wrappers: dict[str, Wrapper] | None = None,
        db_path: str | None = None,
        persist: bool = True,
    ) -> None:
        self._allowed = load_allowed_tools()
        self._denied = load_denied_actions()
        self._wrappers: dict[str, Wrapper] = dict(wrappers or {})
        self._db_path = db_path
        self._persist = persist
        self._policy_version = _policy_version()

    # -- public registry views (metadata only) ---------------------------------- #
    @property
    def allowed_tool_names(self) -> list[str]:
        return sorted(self._allowed)

    @property
    def denied_actions(self) -> list[str]:
        return sorted(self._denied)

    @property
    def wrappers_registered(self) -> int:
        return len(self._wrappers)

    # -- dispatch --------------------------------------------------------------- #
    def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        client_name: str | None = None,
    ) -> dict[str, Any]:
        """Route one tool request through the policy gate; return a safe envelope."""
        correlation_id = uuid.uuid4().hex
        name = (tool_name or "").strip()
        args = arguments if arguments is not None else {}

        try:
            # 2. deny first — explicit denied action by name, or a denied token in args.
            # The denial receipt names the specific denied action (the tool name when the
            # tool itself is denied, or the matched denied token when it rides in arguments).
            if name in self._denied:
                return self._deny(name, REASON_ACTION_DENIED, args, correlation_id, client_name)
            denied_token = self._denied_token_in_args(args)
            if denied_token is not None:
                return self._deny(
                    denied_token, REASON_ACTION_DENIED, args, correlation_id, client_name
                )

            # 3. allowed registry.
            spec = self._allowed.get(name)
            if spec is None:
                return self._deny(name, REASON_TOOL_NOT_ALLOWED, args, correlation_id, client_name)

            # 4. argument validation.
            arg_error = self._validate_arguments(args)
            if arg_error is not None:
                return self._deny(name, REASON_INVALID_ARGUMENTS, args, correlation_id, client_name)

            # 5. wrapper present?
            wrapper = self._wrappers.get(name)
            if wrapper is None:
                return self._deny(
                    name, REASON_WRAPPER_UNAVAILABLE, args, correlation_id, client_name
                )

            # Phase 10A P09: pre-gate raw_* packet_type requests (fail-closed unless mcp_allow_raw_content + permissive)
            pkt_type = str(args.get("packet_type") or "").strip()
            requesting_raw = pkt_type.startswith("raw_")
            mcp_raw_ok = _compute_mcp_raw_allowed()
            if requesting_raw and not mcp_raw_ok:
                return self._deny(name, "raw_content_disabled", args, correlation_id, client_name)

            # 6. invoke wrapper (fail-closed on any exception; no raw error echoed).
            try:
                raw_result = wrapper(dict(args))
            except Exception:  # noqa: BLE001 - fail-closed; never surface raw error text
                return self._deny(name, REASON_BROKER_ERROR, args, correlation_id, client_name)

            # 7. bound + no-raw validate output.
            # When the request is for an explicitly-allowed raw packet, relax the strict no-raw assert (builders still bound + provenance; secrets/PEMs still blocked).
            try:
                if requesting_raw and mcp_raw_ok:
                    bounded = self._bound_output(raw_result, allow_raw=True)
                else:
                    bounded = self._bound_output(raw_result)
            except _UnsafeOutput:
                return self._deny(name, REASON_UNSAFE_OUTPUT, args, correlation_id, client_name)

            # 8. allowed receipt + safe envelope.
            return self._allow(name, spec, args, bounded, correlation_id, client_name)
        except Exception:  # noqa: BLE001 - any unexpected error is a fail-closed denial
            return self._deny(name, REASON_BROKER_ERROR, args, correlation_id, client_name)

    # -- helpers ---------------------------------------------------------------- #
    def _denied_token_in_args(self, args: dict[str, Any]) -> str | None:
        try:
            blob = json.dumps(args, default=str).lower()
        except (TypeError, ValueError):
            return None
        for action in self._denied:
            if action.lower() in blob:
                return action
        return None

    def _validate_arguments(self, args: Any) -> str | None:
        if not isinstance(args, dict):
            return "arguments_not_an_object"
        try:
            encoded = json.dumps(args, default=str)
        except (TypeError, ValueError):
            return "arguments_not_serializable"
        if len(encoded.encode("utf-8")) > _MAX_ARGS_BYTES:
            return "arguments_too_large"
        return None

    def _bound_output(self, result: Any, *, allow_raw: bool = False) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise _UnsafeOutput("wrapper result is not an object")
        results = result.get("results")
        if isinstance(results, list):
            bounded_results = list(results[:MAX_RESULTS])
            result_count = len(bounded_results)
        else:
            bounded_results = []
            result_count = int(result.get("result_count", 0) or 0)
        source_count = int(result.get("source_count", 0) or 0)
        classification = str(result.get("output_classification", "bounded_summary"))

        bounded = dict(result)
        if isinstance(results, list):
            bounded["results"] = bounded_results
        bounded["result_count"] = result_count
        bounded["source_count"] = source_count
        bounded["output_classification"] = classification

        if allow_raw:
            # P09: raw-capable packet explicitly allowed by policy; the wrapper/raw builder is responsible for bounds + provenance + no secrets.
            # Still tag for visibility.
            bounded.setdefault("raw_content", True)
            bounded.setdefault("mcp_raw_exposure", "per_policy")
            return bounded

        # Fail-closed: no forbidden raw pattern may leak through the output.
        try:
            _assert_no_raw(json.dumps(bounded, default=str), "mcp tool output")
        except ValueError as exc:
            raise _UnsafeOutput(str(exc)) from exc
        return bounded

    def _deny(
        self,
        requested_action: str,
        reason_code: str,
        args: dict[str, Any],
        correlation_id: str,
        client_name: str | None,
    ) -> dict[str, Any]:
        receipt_id: str | None = None
        if self._persist:
            receipt_id = write_mcp_denial_receipt(
                requested_action=requested_action or "(unnamed)",
                denial_reason_code=reason_code,
                policy_version=self._policy_version,
                client_name=client_name,
                correlation_id=correlation_id,
                request_hash=_sha256({"tool": requested_action, "args": args}),
                db_path=self._db_path,
            )
        return {
            "tool": requested_action,
            "decision": "denied",
            "denied": True,
            "reason_code": reason_code,
            "receipt_id": receipt_id,
            "correlation_id": correlation_id,
            "policy_posture": dict(_POLICY_POSTURE),
        }

    def _allow(
        self,
        tool_name: str,
        spec: dict[str, Any],
        args: dict[str, Any],
        bounded: dict[str, Any],
        correlation_id: str,
        client_name: str | None,
    ) -> dict[str, Any]:
        result_count = int(bounded.get("result_count", 0))
        source_count = int(bounded.get("source_count", 0))
        classification = str(bounded.get("output_classification", "bounded_summary"))
        receipt_id: str | None = None
        if self._persist:
            receipt_id = write_mcp_tool_call_receipt(
                tool_name=tool_name,
                decision="allowed",
                workflow_wrapper=str(spec.get("wrapper")),
                policy_version=self._policy_version,
                output_classification=classification,
                source_count=source_count,
                result_count=result_count,
                args_hash=_sha256(args),
                result_hash=_sha256(bounded),
                client_name=client_name,
                correlation_id=correlation_id,
                db_path=self._db_path,
            )
        env: dict[str, Any] = {
            "tool": tool_name,
            "decision": "allowed",
            "denied": False,
            "status": str(bounded.get("status", "ok")),
            "output_classification": classification,
            "source_count": source_count,
            "result_count": result_count,
            "provenance": bounded.get("provenance"),
            "policy_posture": dict(_POLICY_POSTURE),
            "receipt_id": receipt_id,
            "correlation_id": correlation_id,
            "result": bounded,
        }
        # P09: when raw exposure was permitted for this call, surface it explicitly in the envelope
        if bounded.get("raw_content") or bounded.get("mcp_raw_exposure"):
            env["policy_posture"] = {
                **env.get("policy_posture", {}),
                "no_raw": False,
                "raw_content_permitted": True,
            }
            env["raw_content"] = True
        return env


class _UnsafeOutput(Exception):
    """Internal: wrapper output failed bounding / no-raw validation."""
