"""Prompt Preflight — centralized executability evaluator and extended authorization schema."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def _auth(prompt: str, **kwargs: object) -> dict:
    return route_prompt(prompt, **kwargs)["authorization"]


def test_authorization_schema_includes_runtime_policy_and_capability_gates() -> None:
    auth = _auth("Search my work files.")
    assert "runtime_policy_permission" in auth
    assert set(auth["runtime_policy_permission"]) >= {
        "safe_mode", "token_scope_allowed", "profile_enabled", "gateway_allowlisted",
        "surface_available", "directly_exposed", "recommended_call_mode",
    }
    assert "recommended_call_mode" in auth
    assert "capability_gates" in auth
    assert set(auth["capability_gates"]) >= {"index", "deploy", "archive", "external_action"}
    assert auth["capability_gates"]["index"]["allowed"] is True
    assert "argument_extraction" in auth
    assert "write_blocked_by_staleness" in auth


def test_read_route_executable_when_surface_stale() -> None:
    auth = _auth(
        "Search my work files.",
        freshness={"stale": True, "staleness_state": "stale"},
    )
    assert auth["read_tool_calls_authorized"] is True
    assert auth["currently_executable"] is True
    assert auth["write_blocked_by_staleness"] is False


def test_write_route_blocked_by_surface_staleness() -> None:
    auth = _auth(
        "document this session: capture budget decision",
        freshness={"stale": True, "staleness_state": "stale"},
    )
    assert auth["write_blocked_by_staleness"] is True
    assert auth["currently_executable"] is False
    assert auth["execution_blocked_reason"] == "surface_stale"


def test_write_route_blocked_by_safe_mode() -> None:
    auth = _auth(
        "document this session: capture budget decision",
        runtime_policy={"safe_mode": True},
    )
    assert auth["runtime_policy_permission"]["safe_mode"] is True
    assert auth["currently_executable"] is False
    assert auth["execution_blocked_reason"] == "safe_mode_active"


def test_surface_unavailable_blocks_execution() -> None:
    auth = _auth(
        "Search my work files.",
        available_tools=frozenset({"assistant_source_file_search"}),
    )
    assert auth["runtime_policy_permission"]["surface_available"] is True
    assert auth["currently_executable"] is True

    auth2 = _auth(
        "Search my work files.",
        available_tools=frozenset({"assistant_search_sources"}),
    )
    assert auth2["runtime_policy_permission"]["surface_available"] is False
    assert auth2["currently_executable"] is False
    assert auth2["execution_blocked_reason"] == "surface_unavailable"


def test_capability_gates_reflect_prompt_prohibitions() -> None:
    auth = _auth(
        "Conduct a read-only repo-truth audit.\n"
        "Do not write, stage, promote, refresh, index, deploy, or mutate anything."
    )
    assert auth["capability_gates"]["index"]["allowed"] is False
    assert auth["capability_gates"]["deploy"]["allowed"] is False
    assert auth["capability_gates"]["index"]["blocked_reason"] == "prompt_prohibits_index"


def test_token_scope_denied_blocks_execution() -> None:
    auth = _auth(
        "Search my work files.",
        runtime_policy={"token_scope_allowed": False},
    )
    assert auth["currently_executable"] is False
    assert auth["execution_blocked_reason"] == "token_scope_denied"


def test_direct_status_tool_executable_without_gateway_allowlist() -> None:
    """Audit row 1 / F-009: hb_mcp_status is direct MCP — not gateway_denied."""
    plan = route_prompt(
        "Conduct a read-only repo-truth audit.\n"
        "Do not write, stage, promote, refresh, index, deploy, or mutate anything."
    )
    auth = plan["authorization"]
    assert plan["recommended_workflow"] == "read_only_surface_audit"
    assert plan["next_step"]["tool"] == "hb_mcp_status"
    assert plan["recommended_call_mode"] == "direct"
    assert auth["recommended_call_mode"] == "direct"
    assert auth["runtime_policy_permission"]["directly_exposed"] is True
    assert auth["runtime_policy_permission"]["gateway_allowlisted"] is False
    assert auth["currently_executable"] is True
    assert auth["execution_blocked_reason"] is None


def test_status_check_hb_mcp_status_uses_direct_call_mode() -> None:
    plan = route_prompt("Is the server up?")
    assert plan["recommended_workflow"] == "status_check"
    assert plan["next_step"]["tool"] == "hb_mcp_status"
    assert plan["recommended_call_mode"] == "direct"
    assert plan["authorization"]["currently_executable"] is True


def test_gateway_only_tool_still_blocked_when_not_allowlisted() -> None:
    auth = _auth(
        "Search my work files.",
        runtime_policy={
            "directly_exposed": False,
            "gateway_allowlisted": False,
            "profile_enabled": True,
            "surface_available": True,
            "recommended_call_mode": "gateway",
        },
    )
    assert auth["currently_executable"] is False
    assert auth["execution_blocked_reason"] == "gateway_denied"


def test_direct_call_mode_skips_gateway_denied_even_when_not_allowlisted() -> None:
    auth = _auth(
        "Is the server up?",
        runtime_policy={
            "directly_exposed": True,
            "gateway_allowlisted": False,
            "profile_enabled": True,
            "surface_available": True,
            "recommended_call_mode": "direct",
        },
    )
    assert auth["currently_executable"] is True
    assert auth["execution_blocked_reason"] is None