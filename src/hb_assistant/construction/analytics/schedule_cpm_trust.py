"""PM-safe CPM trust fields and failure redaction."""

from __future__ import annotations

from typing import Any

_CPM_FAILURE_MESSAGES: dict[str, str] = {
    "cpm_chain_failed": "Computed CPM could not finish for this schedule version. Review technical diagnostics or retry recompute.",
    "cpm_recompute_exception": "Computed CPM recompute did not complete. Retry from import status or contact an operator.",
}

_STEP_HINTS: dict[str, str] = {
    "graph_diagnostics": "graph diagnostics",
    "forward_pass": "forward pass",
    "backward_pass": "backward pass",
    "float": "float calculation",
    "longest_path": "longest-path analysis",
    "criticality": "criticality classification",
}


def redact_cpm_failure_message(
    *,
    failure_code: str | None,
    failed_step: str | None = None,
    raw_message: str | None = None,
) -> str | None:
    """Return PM-safe failure copy. Raw exception text must not be returned."""
    if not failure_code and not failed_step and not raw_message:
        return None
    code = str(failure_code or "cpm_chain_failed")
    base = _CPM_FAILURE_MESSAGES.get(code, _CPM_FAILURE_MESSAGES["cpm_chain_failed"])
    step = str(failed_step or "").strip()
    if step:
        hint = _STEP_HINTS.get(step, step.replace("_", " "))
        return f"{base} Failed during {hint}."
    return base


def map_cpm_trust_status(*, cpm_status: str) -> str:
    status = str(cpm_status or "unavailable")
    if status == "failed":
        return "blocked"
    if status in {"partial", "pending", "unavailable"}:
        return "degraded"
    if status in {"complete"}:
        return "ready"
    if status == "not_started":
        return "unavailable"
    return "degraded"


def public_cpm_trust_fields(
    *,
    observability: dict[str, Any] | None,
    cpm_recompute_status: str,
    trigger_source: str | None = None,
) -> dict[str, Any]:
    """PM-facing CPM trust block — never includes raw failure_message."""
    obs = observability or {}
    status = str(obs.get("status") or cpm_recompute_status or "unavailable")
    failure_code = obs.get("failure_code")
    failed_step = obs.get("failed_step")
    out: dict[str, Any] = {
        "cpm_trust_status": map_cpm_trust_status(cpm_status=status),
        "cpm_recompute_status": status,
        "trigger_source": trigger_source or obs.get("trigger_source"),
        "failed_step": failed_step,
        "failure_code": failure_code,
        "failure_message_redacted": redact_cpm_failure_message(
            failure_code=str(failure_code) if failure_code else None,
            failed_step=str(failed_step) if failed_step else None,
            raw_message=None,
        ),
        "canonical_input_activity_count": obs.get("canonical_input_activity_count"),
        "canonical_input_relationship_count": obs.get("canonical_input_relationship_count"),
        "graph_node_count": obs.get("graph_node_count"),
        "graph_edge_count": obs.get("graph_edge_count"),
        "duration_ms": obs.get("duration_ms"),
    }
    return out


def technical_cpm_diagnostics(observability: dict[str, Any] | None) -> dict[str, Any]:
    """Operator-only diagnostics including raw failure text."""
    if not observability:
        return {}
    return {
        "import_id": observability.get("import_id"),
        "package_id": observability.get("package_id"),
        "schedule_version_key": observability.get("schedule_version_key"),
        "cpm_run_id": observability.get("cpm_run_id"),
        "failure_message_raw": observability.get("failure_message"),
        "failed_step": observability.get("failed_step"),
        "failure_code": observability.get("failure_code"),
        "diagnostics": observability.get("diagnostics") or {},
    }
