"""Phase 07C Prompt 05 — `graph files classify-document-cards` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.store.repositories import ConstructionStore

runner = CliRunner()


def _seed(store: ConstructionStore) -> None:
    for key, ext, name, path in [
        ("k1", "dwg", "site.dwg", "/General"),
        ("k2", "pdf", "doc.pdf", "/Project/RFIs"),
        ("k3", "pdf", "summary.pdf", "/General"),
    ]:
        store.upsert_inventory_item(
            source_key="sp",
            drive_id="d",
            item_id=key,
            name=name,
            web_url="https://x/" + key,
            parent_path=path,
            size_bytes=1024,
            is_folder=False,
            last_modified=None,
            etag="e",
        )
        store.upsert_document_card(
            card_id=key,
            document_card_id=key,
            source_id="sp",
            drive_item_id=key,
            file_extension=ext,
        )


def test_dry_run_then_apply_then_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = str(tmp_path / "cli.sqlite")
    _seed(ConstructionStore(db))
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )

    result = runner.invoke(app, ["files", "classify-document-cards", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files classify-document-cards"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["classified"] == 3
    assert payload["guardrails"]["model_invoked"] is False
    assert ConstructionStore(db).count_document_classification_candidates() == 0

    result = runner.invoke(app, ["files", "classify-document-cards", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "apply"
    assert ConstructionStore(db).count_document_classification_candidates() == 3

    runner.invoke(app, ["files", "classify-document-cards", "--apply", "--json"])
    assert ConstructionStore(db).count_document_classification_candidates() == 3
