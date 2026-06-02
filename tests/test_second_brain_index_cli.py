"""Phase 08A Synthesized Prompt 05 — `second-brain index obsidian` CLI (offline)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _redirect_db(monkeypatch: pytest.MonkeyPatch, db_path: str) -> None:
    from hb_assistant.construction.second_brain.obsidian_index import indexer as idx_mod
    from hb_assistant.store import migrator as mig_mod

    real = mig_mod.get_connection

    def _get(_: object = None):  # type: ignore[no-untyped-def]
        from pathlib import Path

        return real(Path(db_path))

    monkeypatch.setattr(idx_mod, "get_connection", _get)
    monkeypatch.setattr(mig_mod, "get_connection", _get)


def test_index_obsidian_dry_run(runner: CliRunner, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _redirect_db(monkeypatch, str(tmp_path / "cli.sqlite"))
    result = runner.invoke(app, ["second-brain", "index", "obsidian", "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "dry_run"
    assert payload["manifest_id"]
    assert len(payload["approved_roots"]) == 4
    assert payload["guardrails"]["source_notes_mutated"] is False


def test_index_obsidian_apply(runner: CliRunner, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _redirect_db(monkeypatch, str(tmp_path / "cli.sqlite"))
    result = runner.invoke(app, ["second-brain", "index", "obsidian", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "apply"


def test_index_obsidian_mutual_exclusion(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "index", "obsidian", "--dry-run", "--apply", "--json"]
    )
    assert result.exit_code == 2
    assert json.loads(result.output)["error"] == "mutually_exclusive"


def test_index_obsidian_no_raw_content(runner: CliRunner, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _redirect_db(monkeypatch, str(tmp_path / "cli.sqlite"))
    out = runner.invoke(app, ["second-brain", "index", "obsidian", "--dry-run", "--json"]).output
    for forbidden in ("raw_body", "signed_url", "download_url", "http://"):
        assert forbidden not in out
