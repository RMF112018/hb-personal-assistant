"""Phase 06A Prompt 15 — operator command surface: status, help, dry-run defaults.

Asserts the new `graph files status` dashboard, the hardened group help, and that
write-capable commands keep dry-run as the default (a regression guard).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_SID = "sp_2023projects_23_435_01_tropical_sl"


def _patch_empty_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = str(tmp_path / "status.sqlite")
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )


# --- status --------------------------------------------------------------------


def test_status_reports_posture_and_guardrails(tmp_path: Path, monkeypatch) -> None:
    _patch_empty_store(monkeypatch, tmp_path)
    result = runner.invoke(app, ["files", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files status"
    assert payload["ok"] is True
    # Delegated-auth posture: scope names only, no tokens.
    assert payload["delegated_auth"]["configured_delegated_scopes"]
    assert (
        "token" not in json.dumps(payload).lower()
        or "token_acquisition" in payload["delegated_auth"]
    )
    # Source counts from the real registry.
    assert payload["sources"]["registry_total"] >= 1
    assert payload["sources"]["by_system"]
    assert payload["sources"]["projected_v5"] == 0  # empty store
    assert payload["operational"]["review_queue_open"] == 0
    # Standing guardrails.
    g = payload["guardrails"]
    assert g["writeback"] == "none"
    assert g["graph_calls"] == "none"
    assert g["microsoft_365_writeback_enabled"] is False
    assert g["dry_run_default"] is True
    assert g["permission_tightening"] == "deferred"


def test_status_does_not_leak_tokens(tmp_path: Path, monkeypatch) -> None:
    _patch_empty_store(monkeypatch, tmp_path)
    result = runner.invoke(app, ["files", "status", "--json"])
    blob = result.output
    assert "Bearer " not in blob
    assert "access_token" not in blob and "refresh_token" not in blob


# --- dry-run default semantics (regression guard) ------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["files", "ingestion-policy", "--source", _SID, "--json"],
        ["files", "obsidian", "--source", _SID, "--json"],
        ["files", "extract", "--source", _SID, "--json"],
    ],
)
def test_write_capable_commands_default_to_dry_run(
    tmp_path: Path, monkeypatch, argv: list[str]
) -> None:
    _patch_empty_store(monkeypatch, tmp_path)
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "dry_run"


# --- hardened help -------------------------------------------------------------


def test_group_help_documents_side_effect_flags() -> None:
    result = runner.invoke(app, ["files", "--help"])
    assert result.exit_code == 0
    out = result.output
    assert "dry-run" in out.lower() or "dry run" in out.lower()
    for flag in ("--apply", "--download", "--extract"):
        assert flag in out


def test_status_help_ok() -> None:
    result = runner.invoke(app, ["files", "status", "--help"])
    assert result.exit_code == 0
