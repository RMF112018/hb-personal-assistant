"""Shared route-proof expectation evaluator for matrix generators and pytest harnesses."""

from __future__ import annotations

from typing import Any

SUPPORTED_EXPECTATION_KEYS = frozenset({
    "workflow",
    "workflow_not",
    "workflow_in",
    "read_authorized",
    "staging_authorized",
    "staging_authorized_or_write_class",
    "write_authorized",
    "promotion_authorized",
    "external_action_authorized",
    "prohibitions_include",
    "prohibitions_exclude",
    "tools_include",
    "tools_empty",
    "per_tool_groups",
    "per_tool_families",
    "require_route_schema_v2",
    "currently_executable",
    "execution_blocked_reason_in",
    "operation_requested",
    "confidence_in",
    "next_step_tool",
    "arguments_include",
    "prompt_permission_promote",
    "operation_modality_in",
})


def route_actual(plan: dict[str, Any]) -> dict[str, Any]:
    auth = plan.get("authorization") or {}
    steps: list[dict[str, Any]] = []
    if plan.get("next_step"):
        steps.append(plan["next_step"])
    steps.extend(plan.get("additional_steps") or [])
    next_step = plan.get("next_step") or {}
    return {
        "route_schema_version": plan.get("route_schema_version"),
        "workflow": plan.get("recommended_workflow"),
        "family": plan.get("primary_family"),
        "tools": list(plan.get("recommended_tools") or []),
        "read_authorized": auth.get("read_tool_calls_authorized"),
        "advisory": auth.get("advisory_planning_authorized"),
        "staging_authorized": auth.get("staging_authorized"),
        "write_authorized": auth.get("write_authorized"),
        "promotion_authorized": auth.get("promotion_authorized"),
        "external_action_authorized": auth.get("external_action_authorized"),
        "prohibitions": list(auth.get("prohibitions") or []),
        "prompt_authorizes_execution": auth.get("prompt_authorizes_execution"),
        "operation_requested": auth.get("operation_requested") or auth.get("action_class"),
        "prompt_permission": auth.get("prompt_permission"),
        "prompt_permission_promote": (auth.get("prompt_permission") or {}).get("promote"),
        "server_policy_permission": auth.get("server_policy_permission"),
        "approval_satisfied": auth.get("approval_satisfied"),
        "currently_executable": auth.get("currently_executable"),
        "execution_blocked_reason": auth.get("execution_blocked_reason"),
        "operation_modality": auth.get("operation_modality"),
        "next_step_tool": next_step.get("tool"),
        "next_step_arguments": dict(next_step.get("arguments") or {}),
        "next_step": plan.get("next_step"),
        "additional_steps": plan.get("additional_steps"),
        "per_tool_groups": {s.get("tool"): s.get("tool_group") for s in steps if s.get("tool")},
        "per_tool_families": {s.get("tool"): s.get("family") for s in steps if s.get("tool")},
        "confidence": plan.get("route_confidence"),
        "freshness_state": (plan.get("freshness") or {}).get("staleness_state"),
    }


def evaluate_route_expectations(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    unknown = sorted(set(expected) - SUPPORTED_EXPECTATION_KEYS)
    if unknown:
        mismatches.append(f"unsupported_expectation_keys:{unknown}")
        return mismatches

    if "workflow" in expected and actual.get("workflow") != expected["workflow"]:
        mismatches.append(f"workflow: expected {expected['workflow']!r} got {actual.get('workflow')!r}")
    if "workflow_not" in expected and actual.get("workflow") == expected["workflow_not"]:
        mismatches.append(f"workflow_not: got forbidden {expected['workflow_not']!r}")
    if "workflow_in" in expected and actual.get("workflow") not in expected["workflow_in"]:
        mismatches.append(f"workflow_in: got {actual.get('workflow')!r} not in {expected['workflow_in']!r}")
    if "operation_requested" in expected and actual.get("operation_requested") != expected["operation_requested"]:
        mismatches.append(
            f"operation_requested: expected {expected['operation_requested']!r} "
            f"got {actual.get('operation_requested')!r}"
        )
    if "read_authorized" in expected and actual.get("read_authorized") is not expected["read_authorized"]:
        mismatches.append(
            f"read_authorized: expected {expected['read_authorized']!r} got {actual.get('read_authorized')!r}"
        )
    if "staging_authorized" in expected and actual.get("staging_authorized") is not expected["staging_authorized"]:
        mismatches.append(
            f"staging_authorized: expected {expected['staging_authorized']!r} "
            f"got {actual.get('staging_authorized')!r}"
        )
    if expected.get("staging_authorized_or_write_class") is True:
        ok = (
            actual.get("staging_authorized") is True
            or actual.get("operation_requested") == "staged_write"
            or any("stage" in str(t) for t in (actual.get("tools") or []))
        )
        if not ok:
            mismatches.append(
                "staging_authorized_or_write_class: expected staging_authorized "
                f"or staged_write (got op={actual.get('operation_requested')!r} "
                f"stage={actual.get('staging_authorized')!r} tools={actual.get('tools')!r})"
            )
    if "write_authorized" in expected and actual.get("write_authorized") is not expected["write_authorized"]:
        mismatches.append(
            f"write_authorized: expected {expected['write_authorized']!r} got {actual.get('write_authorized')!r}"
        )
    if expected.get("promotion_authorized") is False and actual.get("promotion_authorized") is not False:
        mismatches.append("promotion_authorized: expected False")
    if expected.get("external_action_authorized") is False and actual.get("external_action_authorized") is not False:
        mismatches.append("external_action_authorized: expected False")
    if "currently_executable" in expected and actual.get("currently_executable") is not expected["currently_executable"]:
        mismatches.append(
            f"currently_executable: expected {expected['currently_executable']!r} "
            f"got {actual.get('currently_executable')!r} "
            f"(blocked={actual.get('execution_blocked_reason')!r})"
        )
    if "execution_blocked_reason_in" in expected:
        allowed = expected["execution_blocked_reason_in"]
        got = actual.get("execution_blocked_reason")
        if got not in allowed:
            mismatches.append(f"execution_blocked_reason: got {got!r} not in {allowed!r}")
    for cap in expected.get("prohibitions_include") or []:
        if cap not in (actual.get("prohibitions") or []):
            mismatches.append(f"prohibitions_include missing: {cap}")
    for cap in expected.get("prohibitions_exclude") or []:
        if cap in (actual.get("prohibitions") or []):
            mismatches.append(f"prohibitions_exclude present: {cap}")
    for tool in expected.get("tools_include") or []:
        if tool not in (actual.get("tools") or []):
            mismatches.append(f"tools_include missing: {tool}")
    if expected.get("tools_empty") is True and (actual.get("tools") or []):
        mismatches.append(f"tools_empty: expected [] got {actual.get('tools')!r}")
    for tool, group in (expected.get("per_tool_groups") or {}).items():
        got = (actual.get("per_tool_groups") or {}).get(tool)
        if got != group:
            mismatches.append(f"per_tool_groups[{tool}]: expected {group!r} got {got!r}")
    for tool, fam in (expected.get("per_tool_families") or {}).items():
        got = (actual.get("per_tool_families") or {}).get(tool)
        if got != fam:
            mismatches.append(f"per_tool_families[{tool}]: expected {fam!r} got {got!r}")
    if expected.get("require_route_schema_v2") and actual.get("route_schema_version") != 2:
        mismatches.append(f"route_schema_version: expected 2 got {actual.get('route_schema_version')!r}")
    if "confidence_in" in expected and actual.get("confidence") not in expected["confidence_in"]:
        mismatches.append(f"confidence: got {actual.get('confidence')!r}")
    if "next_step_tool" in expected and actual.get("next_step_tool") != expected["next_step_tool"]:
        mismatches.append(
            f"next_step_tool: expected {expected['next_step_tool']!r} got {actual.get('next_step_tool')!r}"
        )
    for key, val in (expected.get("arguments_include") or {}).items():
        got = (actual.get("next_step_arguments") or {}).get(key)
        if got != val:
            mismatches.append(f"arguments_include[{key}]: expected {val!r} got {got!r}")
    if "prompt_permission_promote" in expected:
        if actual.get("prompt_permission_promote") is not expected["prompt_permission_promote"]:
            mismatches.append(
                f"prompt_permission_promote: expected {expected['prompt_permission_promote']!r} "
                f"got {actual.get('prompt_permission_promote')!r}"
            )
    if "operation_modality_in" in expected and actual.get("operation_modality") not in expected["operation_modality_in"]:
        mismatches.append(
            f"operation_modality: got {actual.get('operation_modality')!r} "
            f"not in {expected['operation_modality_in']!r}"
        )
    return mismatches