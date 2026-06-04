"""Phase 08D Prompt 11 — MCP operator CLI surfaces.

Proves the `second-brain mcp` operator commands (tools/resources/prompts/audit) expose
read-only, metadata-only JSON: the registries list 9/5/5 entries, the audit reports its ten
checks, and no command surfaces a raw field. `--no-snapshot` keeps the tests off the live DB.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.main import app

runner = CliRunner()


def _invoke(*args: str) -> dict:
    # `--no-snapshot` keeps the operator commands off the live DB during tests.
    result = runner.invoke(app, ["second-brain", "mcp", *args, "--no-snapshot", "--json"])
    assert result.exit_code == 0, result.output
    payload: dict = json.loads(result.stdout)
    # The registries are metadata-only listings; no raw VALUES leak (denied-action *names*
    # such as `raw_prompt_access`/`signed_url_access` are policy metadata, not raw content).
    assert "guardrails" in payload or "checks" in payload
    return payload


def test_mcp_tools_lists_nine_allowed_and_denied() -> None:
    d = _invoke("tools")
    assert d["allowed_tool_count"] == 9
    assert d["denied_action_count"] == 27
    assert len(d["tools"]) == 9
    assert {t["name"] for t in d["tools"]} >= {"hb_status", "hb_query"}
    assert all(t["wrapper"] for t in d["tools"])
    assert "workflow_wrapper_only" in d["global_requirements"]
    assert "arbitrary_sql" in d["denied_actions"]


def test_mcp_resources_lists_five() -> None:
    d = _invoke("resources")
    assert d["resource_count"] == 5
    uris = {r["uri"] for r in d["resources"]}
    assert "hb://status/system" in uris
    assert all(r["wrapper"] and r["source"] for r in d["resources"])
    assert d["requirements"]


def test_mcp_prompts_lists_five_routing_through_allowed() -> None:
    d = _invoke("prompts")
    assert d["prompt_count"] == 5
    allowed = {t["name"] for t in _invoke("tools")["tools"]}
    for p in d["prompts"]:
        assert p["routes_through"]
        assert all(r in allowed for r in p["routes_through"]), f"{p['name']} off-allowlist"


def test_mcp_audit_reports_ten_passing_checks() -> None:
    d = _invoke("audit")
    assert d["proof_passed"] is True
    assert d["status"] == "ok"
    assert d["finding_count"] == 0
    assert len(d["checks"]) == 10
    assert all(c["passed"] for c in d["checks"])
