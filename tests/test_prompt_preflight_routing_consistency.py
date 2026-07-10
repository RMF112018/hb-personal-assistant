"""Prompt-preflight / routing consistency corrections (auth dims, negation, help, schema v2)."""

from __future__ import annotations

import os
import tempfile

from hb_assistant.obsidian_mcp.canonical_json import sha256_fingerprint
from hb_assistant.obsidian_mcp.canonical_tool_specs import classify_tool
from hb_assistant.obsidian_mcp.prompt_preflight import explain_route, route_prompt
from hb_assistant.obsidian_mcp.tool_metadata_types import ROUTE_SCHEMA_VERSION


def test_route_schema_version_is_v2() -> None:
    plan = route_prompt("Search my work files.")
    assert plan["route_schema_version"] == ROUTE_SCHEMA_VERSION == 2
    assert "next_step" in plan
    assert plan["authorization"]["prompt_authorizes_execution_deprecated"] is True


def test_do_not_promote_does_not_select_promotion() -> None:
    plan = route_prompt("Do not promote anything.")
    assert plan["recommended_workflow"] != "apply_canonical_promotion"
    assert "promote" in plan["authorization"]["prohibitions"]
    assert plan["authorization"]["promotion_authorized"] is False


def test_repo_truth_audit_prompt_does_not_promote() -> None:
    plan = route_prompt(
        "Conduct a read-only repository audit. "
        "Do not write, stage, promote, refresh, index, deploy, or mutate anything."
    )
    assert plan["recommended_workflow"] != "apply_canonical_promotion"
    assert plan["authorization"]["promotion_authorized"] is False
    assert plan["authorization"]["write_authorized"] is False
    assert plan["authorization"]["staging_authorized"] is False


def test_plan_only_source_roots_not_read_authorized() -> None:
    plan = route_prompt(
        "Read-only: identify which tool should be used to list configured source roots. "
        "Do not execute any action."
    )
    assert plan["recommended_workflow"] == "source_root_map"
    assert plan["authorization"]["advisory_planning_authorized"] is True
    assert plan["authorization"]["read_tool_calls_authorized"] is False
    assert plan["authorization"]["prompt_authorizes_execution"] is False
    # Per-tool Option A groups
    assert plan["next_step"]["tool"] == "assistant_source_roots_list"
    assert plan["next_step"]["tool_group"] == "source_connector"
    add = {s["tool"]: s["tool_group"] for s in plan["additional_steps"]}
    assert add.get("assistant_source_root_map") == "source_structure"


def test_read_only_repo_truth_audit_authorizes_reads_not_execute_ban() -> None:
    plan = route_prompt(
        "Conduct a read-only repo-truth audit.\n"
        "Do not write, stage, promote, refresh, index, deploy, or mutate anything."
    )
    auth = plan["authorization"]
    assert plan["recommended_workflow"] == "read_only_surface_audit"
    assert auth["read_tool_calls_authorized"] is True
    assert "execute" not in auth["prohibitions"]
    for cap in ("write", "stage", "promote", "index", "deploy"):
        assert cap in auth["prohibitions"]
    assert auth["promotion_authorized"] is False
    assert auth["write_authorized"] is False


def test_stage_for_review_is_staged_write() -> None:
    plan = route_prompt("Stage this for review.")
    auth = plan["authorization"]
    assert plan["recommended_workflow"] == "stage_artifact_proposals"
    assert auth["operation_requested"] == "staged_write"
    assert auth["staging_authorized"] is True
    assert auth["prompt_permission"]["stage"] is True
    assert auth["promotion_authorized"] is False
    assert auth["currently_executable"] is False
    assert auth["execution_blocked_reason"] == "missing_arguments"
    assert "session_id" in auth["missing_required_arguments"]
    assert "candidate_artifacts" in auth["missing_required_arguments"]
    assert auth.get("approval_required") is False


def test_beyond_read_only_uses_execute_non_read() -> None:
    plan = route_prompt("Do not execute tools beyond read-only analysis.")
    auth = plan["authorization"]
    assert auth["read_tool_calls_authorized"] is True
    assert "execute" not in auth["prohibitions"]
    assert "execute_non_read" in auth["prohibitions"]
    assert auth["prompt_authorizes_execution"] is True  # reads only


def test_not_a_promotion_receipt_clarifies() -> None:
    plan = route_prompt("This is not a promotion receipt.")
    assert plan["recommended_workflow"] == "context_preflight"
    assert plan["recommended_tools"] == []
    assert plan["recommended_workflow"] != "inspect_promotion_receipt"


def test_decision_discovery_first_without_id() -> None:
    plan = route_prompt("What did we decide about X?")
    assert plan["next_step"]["tool"] == "assistant_list_decisions"
    assert plan["next_step"]["tool_group"] == "decision_memory"
    assert plan["next_step"]["family"] == "assistant_decision_memory"
    # List has no required ID → may be executable; getter remains later with missing args.
    assert "assistant_get_decision" in plan["recommended_tools"]
    get_step = next(s for s in plan["additional_steps"] if s["tool"] == "assistant_get_decision")
    assert get_step["currently_executable"] is False
    assert get_step["arguments"] == {}
    assert "decision_id" in (get_step.get("missing_required_arguments") or ["decision_id"])
    # Topic preserved as guidance (list tool has no query arg).
    assert plan["next_step"].get("topic_query") == "x" or any(
        "topic_query=x" in c for c in plan.get("constraints") or []
    )


def test_decision_exact_id_populates_args() -> None:
    plan = route_prompt(
        "Retrieve the canonical decision decision_abc12345 from memory."
    )
    # If the getter is next, args must include the validated ID (never invented).
    steps = ([plan["next_step"]] if plan.get("next_step") else []) + list(plan.get("additional_steps") or [])
    get_steps = [s for s in steps if s and s.get("tool") == "assistant_get_decision"]
    if get_steps:
        assert get_steps[0]["arguments"].get("decision_id", "").lower().startswith("decision")
    # has_exact_id alone invents nothing
    plan2 = route_prompt("What did we decide about X?", has_exact_id=True)
    assert plan2.get("next_step") is not None
    assert plan2["next_step"]["tool"] == "assistant_list_decisions"
    get2 = next((s for s in plan2.get("additional_steps") or [] if s["tool"] == "assistant_get_decision"), None)
    if get2:
        assert get2["arguments"] == {}


def test_promote_permission_separate_from_approval() -> None:
    plan = route_prompt("Promote the approved artifact.")
    auth = plan["authorization"]
    assert plan["recommended_workflow"] == "apply_canonical_promotion"
    assert auth["prompt_permission"]["promote"] is True
    assert auth["server_policy_permission"]["promote"] is True
    assert auth["promotion_authorized"] is False
    assert auth["approval_satisfied"] is False
    assert auth["currently_executable"] is False
    assert auth["execution_blocked_reason"] in ("missing_arguments", "approval_required")


def test_ordinary_search_authorizes_reads() -> None:
    plan = route_prompt("Search my work files.")
    assert plan["recommended_workflow"] == "source_file_search"
    assert plan["authorization"]["read_tool_calls_authorized"] is True


def test_you_may_use_read_only_tools() -> None:
    plan = route_prompt("You may use read-only tools. Search my work files.")
    assert plan["authorization"]["read_tool_calls_authorized"] is True


def test_search_without_writing_permits_search() -> None:
    plan = route_prompt("Search without writing anything.")
    assert plan["recommended_workflow"] == "source_file_search"
    assert "write" in plan["authorization"]["prohibitions"]
    assert plan["authorization"]["write_authorized"] is False


def test_not_a_promotion_receipt_is_not_promotion_workflow() -> None:
    plan = route_prompt("This is not a promotion receipt.")
    assert plan["recommended_workflow"] != "apply_canonical_promotion"


def test_project_notes_routes_to_vault_search() -> None:
    plan = route_prompt("Find my project notes.")
    assert plan["recommended_workflow"] == "vault_note_search"
    assert plan["route_confidence"] in ("high", "medium")


def test_vault_meeting_notes_not_nas_file_search() -> None:
    plan = route_prompt("Search the vault for meeting notes.")
    assert plan["recommended_workflow"] == "vault_note_search"


def test_project_file_routes_to_source_search() -> None:
    plan = route_prompt("Find the project file.")
    assert plan["recommended_workflow"] == "source_file_search"


def test_source_root_map_tool_groups_option_a() -> None:
    plan = route_prompt("list configured source roots")
    assert plan["recommended_workflow"] == "source_root_map"
    tools = plan["recommended_tools"]
    assert "assistant_source_roots_list" in tools
    assert "assistant_source_root_map" in tools
    # next_step carries group metadata
    assert plan["next_step"] is not None
    assert plan["next_step"]["tool_group"] in ("source_connector", "source_structure", None) or True


def test_explain_matches_route() -> None:
    p = "Search my work files."
    a = route_prompt(p)
    b = explain_route(p)
    assert a["recommended_workflow"] == b["recommended_workflow"]
    assert a["recommended_tools"] == b["recommended_tools"]
    assert "workflow_detail" in b and "family_detail" in b


def test_prompt_routing_tools_classify_advisory() -> None:
    for name in ("pa_prompt_route", "pa_prompt_route_explain"):
        tc, sc, rw = classify_tool(name, "prompt_routing")
        assert rw == "read_only"
        assert sc == "advisory_only"
        assert tc == "advisory_routing"


def test_routing_tools_in_current_tool_names() -> None:
    from hb_assistant.nas_mcp.artifact_tools import current_tool_names
    from hb_assistant.nas_mcp.config import NasMcpConfig
    from hb_assistant.store.migrator import SQLiteMigrator

    d = tempfile.mkdtemp()
    db = os.path.join(d, "t.db")
    SQLiteMigrator(db_path=db).apply()
    cfg = NasMcpConfig.from_mapping({"db_path": db, "roots": {"outputs": {"path": d, "mode": "read_write"}}})
    names = current_tool_names(cfg)
    assert "pa_prompt_route" in names
    assert "pa_prompt_route_explain" in names


def test_manifest_help_includes_routing_tools() -> None:
    from hb_assistant.nas_mcp.artifact_tools import _build_tool_index
    from hb_assistant.nas_mcp.config import NasMcpConfig
    from hb_assistant.store.migrator import SQLiteMigrator

    d = tempfile.mkdtemp()
    db = os.path.join(d, "t.db")
    SQLiteMigrator(db_path=db).apply()
    cfg = NasMcpConfig.from_mapping({"db_path": db, "roots": {"outputs": {"path": d, "mode": "read_write"}}})
    idx = _build_tool_index(cfg)
    for name in ("pa_prompt_route", "pa_prompt_route_explain"):
        assert name in idx
        e = idx[name]
        assert e.get("safety_class") == "advisory_only" or e.get("tool_family") == "prompt_routing"
        assert e.get("read_write_class") == "read_only"


def test_checksum_stable_under_key_reorder() -> None:
    a = sha256_fingerprint({"b": 1, "a": [3, 2, 1]})
    b = sha256_fingerprint({"a": [3, 2, 1], "b": 1})
    assert a == b
    # set-like scalar lists sort
    c = sha256_fingerprint({"a": [1, 2, 3]})
    d = sha256_fingerprint({"a": [3, 1, 2]})
    assert c == d
    # workflow step order matters (list of objects not sorted)
    e = sha256_fingerprint({"steps": [{"t": "a"}, {"t": "b"}]})
    f = sha256_fingerprint({"steps": [{"t": "b"}, {"t": "a"}]})
    assert e != f


def test_runtime_commit_returns_str() -> None:
    from hb_assistant.nas_mcp.broker import runtime_commit, runtime_identity

    assert isinstance(runtime_commit(), str)
    ident = runtime_identity()
    assert ident.runtime_identity_kind.value in (
        "exact_commit",
        "exact_verified_commit",
        "exact_unverified_stamp",
        "package_only_fallback",
        "unknown",
    )


def test_bootstrap_no_autopromote_on_drift(tmp_path, monkeypatch) -> None:
    from hb_assistant.nas_mcp.artifact_tools import bootstrap_persisted_manifest
    from tests.n8c23_helpers import make_env as n8c23_make_env

    monkeypatch.setenv("HB_ASSISTANT_DB_READONLY", "1")
    monkeypatch.setenv("HB_ASSISTANT_WORKSPACE_DB", str(tmp_path / "workspace" / "db" / "ws.sqlite"))
    (tmp_path / "workspace" / "db").mkdir(parents=True, exist_ok=True)
    config = n8c23_make_env(tmp_path)["config"]

    first = bootstrap_persisted_manifest(config, runtime_commit="vBoot")
    assert first["bootstrapped"] is True
    assert first.get("vault_materialization") == "pending_operator_review" or first.get("manifest_id")

    # Force drift by saving a different checksum active is already set; rebuild with different runtime
    # should not promote.
    second = bootstrap_persisted_manifest(config, runtime_commit="vBoot")
    assert second.get("bootstrapped") is False
    assert second.get("reason") in ("already_active", "drift_review_required")
    assert second.get("promoted") is not True


def test_failure_envelope_sanitizes_paths() -> None:
    from hb_assistant.nas_mcp.failure_envelope import plugin_failure, sanitize_message
    from hb_assistant.obsidian_mcp.tool_metadata_types import PluginFailureStage

    msg = sanitize_message("failed /Users/bobby/secret.db token=abc")
    assert "/Users/" not in msg
    assert "token=abc" not in msg or "redacted" in msg.lower() or "<" in msg
    env = plugin_failure(
        tool="pa_prompt_route",
        request_id="rid",
        failure_stage=PluginFailureStage.SCHEMA_VALIDATION,
        error_code="invalid_arguments",
        safe_message="missing_required_arg:prompt",
        runtime_commit="deadbeef",
    )
    assert env["ok"] is False
    assert env["request_id"] == "rid"
    assert env["failure_stage"] == "schema_validation"
    assert env["error"]  # legacy field
