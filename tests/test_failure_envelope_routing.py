"""Failure envelope normalization for gateway and broker deny paths."""

from __future__ import annotations

import pytest

from hb_assistant.nas_mcp.failure_envelope import (
    gateway_plugin_failure,
    map_deny_reason,
    normalize_dispatch_failure,
    plugin_failure,
)
from hb_assistant.obsidian_mcp.tool_metadata_types import PluginFailureStage


@pytest.mark.parametrize(
    ("reason", "stage", "code"),
    [
        ("missing_required_arg:prompt", PluginFailureStage.SCHEMA_VALIDATION, "missing_required_argument"),
        ("missing_required_arg:session_id", PluginFailureStage.SCHEMA_VALIDATION, "missing_required_argument"),
        ("missing_required_args:session_id,candidate_artifacts", PluginFailureStage.SCHEMA_VALIDATION, "missing_required_argument"),
        ("tool_not_registered: assistant_output_stage", PluginFailureStage.BROKER_DISPATCH, "tool_not_registered"),
        ("tool_not_registered:pa_foo", PluginFailureStage.BROKER_DISPATCH, "tool_not_registered"),
        ("unknown_or_non_assistant_tool:bogus", PluginFailureStage.GATEWAY_ALLOWLIST, "gateway_denied"),
        ("not_an_allowlisted_assistant_tool:raw_sql", PluginFailureStage.GATEWAY_ALLOWLIST, "gateway_denied"),
        ("denied_tool:hb_db_select", PluginFailureStage.BROKER_POLICY, "policy_denied"),
        ("tool_name_required", PluginFailureStage.SCHEMA_VALIDATION, "invalid_arguments"),
        ("arguments_must_be_object", PluginFailureStage.SCHEMA_VALIDATION, "invalid_arguments"),
        ("limit_exceeds_max:limit:100000>500", PluginFailureStage.SCHEMA_VALIDATION, "invalid_arguments"),
        ("safe_mode_active:pa_output_stage", PluginFailureStage.BROKER_POLICY, "policy_denied"),
        ("action_denied_by_policy", PluginFailureStage.BROKER_POLICY, "policy_denied"),
        ("tool_not_in_token_scope:pa_output_stage", PluginFailureStage.BROKER_POLICY, "token_scope_denied"),
        ("surface_stale_manifest", PluginFailureStage.SURFACE_STALE, "surface_stale"),
        ("unclassified_internal_fault", PluginFailureStage.BROKER_DISPATCH, "dispatch_denied"),
    ],
)
def test_map_deny_reason_structured_codes(reason: str, stage: PluginFailureStage, code: str) -> None:
    mapped_stage, mapped_code, _retryable = map_deny_reason(reason)
    assert mapped_stage == stage
    assert mapped_code == code


def test_gateway_plugin_failure_pre_broker_shape() -> None:
    env = gateway_plugin_failure(
        tool="raw_sql",
        reason="not_an_allowlisted_assistant_tool:raw_sql",
        gateway_tool="hb_assistant_tool_query",
        request_id="req-gateway-1",
        runtime_commit="abc123",
    )
    assert env["ok"] is False
    assert env["request_id"] == "req-gateway-1"
    assert env["tool"] == "raw_sql"
    assert env["failure_stage"] == "gateway_allowlist"
    assert env["error_code"] == "gateway_denied"
    assert env["reached_gateway"] is True
    assert env["reached_broker"] is False
    assert env["reached_handler"] is False
    assert env["gateway_tool"] == "hb_assistant_tool_query"
    assert "not_an_allowlisted_assistant_tool" in env["safe_message"]


def test_normalize_dispatch_failure_maps_keyerror_to_missing_fields() -> None:
    reason, extra = normalize_dispatch_failure(KeyError("decision_id"))
    assert reason == "missing_required_arg:decision_id"
    assert extra == {"missing_fields": ["decision_id"]}


def test_gateway_missing_required_arg_includes_missing_fields() -> None:
    env = gateway_plugin_failure(
        tool="assistant_get_decision",
        reason="missing_required_arg:decision_id",
        gateway_tool="hb_assistant_tool_query",
    )
    assert env["error_code"] == "missing_required_argument"
    assert env["failure_stage"] == "schema_validation"
    assert env["missing_fields"] == ["decision_id"]
    assert env["safe_message"] == "missing_required_arg:decision_id"


def test_broker_deny_envelope_for_tool_not_registered() -> None:
    stage, code, retryable = map_deny_reason("tool_not_registered: assistant_output_stage")
    env = plugin_failure(
        tool="assistant_output_stage",
        request_id="req-broker-1",
        failure_stage=stage,
        error_code=code,
        safe_message="tool_not_registered: assistant_output_stage",
        retryable=retryable,
        reached_gateway=True,
        reached_broker=True,
        reached_handler=False,
    )
    assert env["failure_stage"] == "broker_dispatch"
    assert env["error_code"] == "tool_not_registered"
    assert env["reached_broker"] is True