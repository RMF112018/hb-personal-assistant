"""Phase 07C Prompt 06 — `graph files match-document-projects` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.store.repositories import ConstructionStore

runner = CliRunner()


def _seed(store: ConstructionStore) -> None:
    # project_key values are deliberately not in the live registry, so each card
    # matches via source-binding-only (deterministic) without depending on registry
    # project numbers. None project_key -> skipped.
    for key, project_key in [
        ("k1", "cli_proj_a"),
        ("k2", "cli_proj_b"),
        ("k3", "cli_proj_a"),
        ("k4", None),
    ]:
        store.upsert_inventory_item(
            source_key="sp", drive_id="d", item_id=key, name="raw_" + key, web_url="https://x/" + key,
            parent_path="/General", size_bytes=1024, is_folder=False, last_modified=None, etag="e",
        )
        store.upsert_document_card(
            card_id=key, document_card_id=key, source_id="sp", drive_item_id=key,
            file_extension="pdf", project_key=project_key,
        )


def test_dry_run_then_apply_then_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "cli.sqlite")
    _seed(ConstructionStore(db))
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )

    result = runner.invoke(app, ["files", "match-document-projects", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files match-document-projects"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["matched"] == 3
    assert payload["summary"]["unmatched_skipped"] == 1
    assert payload["guardrails"]["model_invoked"] is False
    assert ConstructionStore(db).count_document_project_match_candidates() == 0

    result = runner.invoke(app, ["files", "match-document-projects", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "apply"
    assert ConstructionStore(db).count_document_project_match_candidates() == 3

    runner.invoke(app, ["files", "match-document-projects", "--apply", "--json"])
    assert ConstructionStore(db).count_document_project_match_candidates() == 3
