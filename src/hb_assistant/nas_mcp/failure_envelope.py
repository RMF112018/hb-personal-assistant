"""Sanitized plugin-observed failure envelopes.

Only stages the plugin actually observed may be reported. Unobserved client/connector
refusals are documentation concerns — never authoritative envelope stages.
"""

from __future__ import annotations

import re
from typing import Any

from hb_assistant.obsidian_mcp.tool_metadata_types import PluginFailureStage

_ABS_PATH = re.compile(r"(?:/Users/|/home/|/var/|/tmp/|/opt/|[A-Za-z]:\\)")
# Redact credential-like values, not policy reason codes such as ``tool_not_in_token_scope``.
_SECRETISH = re.compile(
    r"(?i)("
    r"password\s*[:=]\s*\S+"
    r"|secret\s*[:=]\s*\S+"
    r"|api[_-]?key\s*[:=]\s*\S+"
    r"|authorization:\s*bearer\s+\S+"
    r"|bearer\s+[A-Za-z0-9\-._~+/]+=*"
    r")"
)


def sanitize_message(text: str, *, max_len: int = 240) -> str:
    s = str(text or "")
    s = _ABS_PATH.sub("<path>", s)
    s = _SECRETISH.sub("<redacted>", s)
    s = s.replace("\n", " ").strip()
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def plugin_failure(
    *,
    tool: str,
    request_id: str,
    failure_stage: PluginFailureStage | str,
    error_code: str,
    safe_message: str,
    retryable: bool = False,
    reached_gateway: bool = True,
    reached_broker: bool = True,
    reached_handler: bool = False,
    runtime_commit: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stage = failure_stage.value if isinstance(failure_stage, PluginFailureStage) else str(failure_stage)
    # Never claim unobserved external stages as plugin truth.
    if stage in ("client_not_observed", "connector_transport", "client_did_not_emit_call"):
        stage = PluginFailureStage.UNKNOWN_INTERNAL.value
    out: dict[str, Any] = {
        "ok": False,
        "request_id": request_id,
        "tool": tool,
        "failure_stage": stage,
        "error_code": error_code,
        "retryable": bool(retryable),
        "safe_message": sanitize_message(safe_message),
        "reached_gateway": bool(reached_gateway),
        "reached_broker": bool(reached_broker),
        "reached_handler": bool(reached_handler),
        "runtime_commit": runtime_commit,
        # Legacy field retained for existing clients.
        "error": sanitize_message(safe_message),
    }
    if extra:
        for k, v in extra.items():
            if k not in out:
                out[k] = v
    return out


def map_deny_reason(reason: str) -> tuple[PluginFailureStage, str, bool]:
    """Map broker deny_reason string → (stage, error_code, retryable)."""
    r = str(reason or "")
    if r.startswith("safe_mode") or "denied_by_policy" in r or "blocked_by_profile" in r:
        return PluginFailureStage.BROKER_POLICY, "policy_denied", False
    if "token_scope" in r or "not_in_token" in r:
        return PluginFailureStage.BROKER_POLICY, "token_scope_denied", False
    if "rate" in r or "concurrency" in r:
        return PluginFailureStage.BROKER_POLICY, "rate_limited", True
    if "missing_required" in r or "invalid" in r or "schema" in r:
        return PluginFailureStage.SCHEMA_VALIDATION, "invalid_arguments", False
    if "stale" in r or "surface" in r:
        return PluginFailureStage.SURFACE_STALE, "surface_stale", False
    if "allowlist" in r or "not_gateway" in r:
        return PluginFailureStage.GATEWAY_ALLOWLIST, "gateway_denied", False
    return PluginFailureStage.BROKER_DISPATCH, "dispatch_denied", False
