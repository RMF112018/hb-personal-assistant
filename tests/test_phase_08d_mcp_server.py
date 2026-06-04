"""Phase 08D MCP server foundation + config-preview surface.

Proves the stdio-only server: the startup checks pass for the landed foundation, both guard
proofs pass live (no-raw-access: Prompt 13; no-writeback: Prompt 14); serve readiness tracks
the optional MCP SDK (Prompt 15 — operational when installed, fail-closed when absent or on
an uninitialized DB); the Claude Desktop config preview is safe + schema-conformant and flags
unsafe variants; and the two V37 metadata-only tables get guard-clean rows. The tests are
SDK-presence-aware so the suite passes both in a base install and with the SDK installed; no
test enters the blocking serve loop.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.mcp import (
    assess_config_safety,
    build_claude_desktop_config_preview,
    build_mcp_status,
    evaluate_startup_checks,
    serve_stdio,
)
from hb_assistant.construction.second_brain.mcp.config_preview import _server_entry
from hb_assistant.construction.second_brain.mcp.store import write_mcp_server_config_snapshot

_GUARD_PROOF_BLOCKER = "mcp_sdk_not_installed"


def test_startup_checks_foundation_passes_both_guard_proofs() -> None:
    report = evaluate_startup_checks()
    assert report["foundation_ok"] is True
    by_name = {c["name"]: c["status"] for c in report["checks"]}
    for name in (
        "schema_version_v37",
        "server_policy_seed_loaded",
        "allowed_tools_registry_present",
        "denied_tools_registry_present",
        "resource_registry_present",
        "prompt_registry_present",
        "permission_policy_fail_closed",
        "transport_stdio_only",
    ):
        assert by_name[name] == "pass", f"{name} should pass"
    # Prompts 13/14: both guard proofs now pass live; nothing is deferred.
    assert by_name["no_raw_access_proof"] == "pass"
    assert by_name["no_writeback_proof"] == "pass"
    assert set(report["deferred"]) == set()


def test_status_serve_readiness_tracks_sdk_presence() -> None:
    import importlib.util

    status = build_mcp_status(persist=False)
    assert status["foundation_ok"] is True
    # Prompt 05: the nine workflow wrappers are registered.
    assert status["mcp_tools_registered"] == 9
    # Prompts 13/14: both guard-proof serve blockers are gone.
    assert "no_raw_access_proof_pending_prompt_13" not in status["serve_blockers"]
    assert "no_writeback_proof_pending_prompt_14" not in status["serve_blockers"]
    # Prompt 15: the optional MCP SDK is the sole remaining serve gate; readiness tracks it.
    if importlib.util.find_spec("mcp") is None:
        assert status["mcp_sdk_available"] is False
        assert status["ready_to_serve"] is False
        assert status["serve_blockers"] == ["mcp_sdk_not_installed"]
    else:
        assert status["mcp_sdk_available"] is True
        assert status["ready_to_serve"] is True
        assert status["serve_blockers"] == []


def test_status_persists_metadata_only_server_config_snapshot() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        status = build_mcp_status(db_path=db, persist=True)
        assert status["snapshot_id"]
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT transport, schema_version, external_writeback_performed, "
            "raw_prompt_persisted, arbitrary_sql_performed "
            "FROM second_brain_mcp_server_config_snapshots"
        ).fetchall()
        assert len(rows) == 1
        transport, schema_version, ext_wb, raw_prompt, arb_sql = rows[0]
        assert transport == "stdio"
        assert schema_version >= 37
        assert (ext_wb, raw_prompt, arb_sql) == (0, 0, 0)


def test_server_config_snapshot_guard_check_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        write_mcp_server_config_snapshot(
            transport="stdio", config_hash="h", policy_version="v1", db_path=db
        )
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "INSERT INTO second_brain_mcp_server_config_snapshots "
                "(snapshot_id, transport, config_hash, policy_version, schema_version, "
                "external_writeback_performed) VALUES ('bad','stdio','h','v1',37,1)"
            )
            raise AssertionError("guard CHECK(external_writeback_performed = 0) not enforced")
        except sqlite3.IntegrityError:
            pass


def test_serve_dry_run_reports_readiness_without_serving() -> None:
    import importlib.util

    # Dry run never enters the stdio loop, so it is hang-safe whether or not the SDK is present.
    result = serve_stdio(dry_run=True)
    assert result["served"] is False
    assert result["transport"] == "stdio"
    if importlib.util.find_spec("mcp") is None:
        assert result["ready_to_serve"] is False
        assert _GUARD_PROOF_BLOCKER in result["reasons"]
    else:
        assert result["ready_to_serve"] is True
        assert result["reasons"] == []


def test_serve_fail_closed_when_not_ready_opens_nothing(monkeypatch) -> None:
    # When the foundation check fails or the SDK is absent, serve refuses without ever
    # entering the loop (served=False) — proven here with a forced not-ready status so the
    # assertion holds deterministically whether or not the SDK is installed.
    import hb_assistant.construction.second_brain.mcp.server as server_mod

    def _not_ready(*_args, **_kwargs):
        return {
            "foundation_ok": False,
            "mcp_sdk_available": False,
            "ready_to_serve": False,
            "serve_blockers": ["mcp_sdk_not_installed"],
            "guardrails": {},
        }

    monkeypatch.setattr(server_mod, "build_mcp_status", _not_ready)
    result = server_mod.serve_stdio()
    assert result["served"] is False
    assert result["ready_to_serve"] is False
    assert "foundation_checks_failed" in result["reasons"]
    assert "mcp_sdk_not_installed" in result["reasons"]


def test_config_preview_is_safe_and_schema_conformant() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        result = build_claude_desktop_config_preview(
            db_path=db, evidence_dir=td, persist=True, write_evidence=True
        )
        assert result["safe"] is True
        assert result["schema_conformant"] is True
        assert result["unsafe_reasons"] == []
        assert result["transport"] == "stdio"
        assert result["env_keys"] == ["HB_MCP_POLICY", "HB_MCP_TRANSPORT"]
        assert result["config_hash"]
        assert result["auto_apply"] is False
        # evidence json written and matches the preview
        written = json.loads((Path(td) / "claude-desktop-config-preview.json").read_text())
        assert written["mcpServers"]["hb-personal-assistant"]["command"] == "hb-assistant"
        assert written["mcpServers"]["hb-personal-assistant"]["args"] == [
            "second-brain",
            "mcp",
            "serve",
            "--stdio",
            "--json",
        ]
        # preview row persisted, safe=1, guard-clean
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT safe, transport, source_system_writeback_performed "
            "FROM second_brain_mcp_claude_desktop_config_previews"
        ).fetchall()
        assert rows == [(1, "stdio", 0)]


def test_config_preview_flags_unsafe_variants() -> None:
    # bad command
    bad_cmd = _server_entry({"HB_MCP_TRANSPORT": "stdio"})
    bad_cmd["mcpServers"]["hb-personal-assistant"]["command"] = "/bin/sh"
    assert assess_config_safety(bad_cmd)["safe"] is False
    assert "unsafe_command" in assess_config_safety(bad_cmd)["unsafe_reasons"]

    # disallowed env key
    bad_env = _server_entry({"HB_MCP_TRANSPORT": "stdio", "AWS_SECRET_ACCESS_KEY": "x"})
    report = assess_config_safety(bad_env)
    assert report["safe"] is False
    assert any(r.startswith("unsafe_env_key:") for r in report["unsafe_reasons"])

    # non-stdio args
    bad_args = _server_entry({"HB_MCP_TRANSPORT": "stdio"})
    bad_args["mcpServers"]["hb-personal-assistant"]["args"] = [
        "second-brain",
        "mcp",
        "serve",
        "--http",
    ]
    report2 = assess_config_safety(bad_args)
    assert report2["safe"] is False
    assert "unsafe_args" in report2["unsafe_reasons"]
    assert "unsupported_transport" in report2["unsafe_reasons"]
