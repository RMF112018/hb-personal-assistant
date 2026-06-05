"""Phase 07C Prompt 09 — `graph files build-document-previews` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.store.repositories import ConstructionStore

runner = CliRunner()


def _seed(store: ConstructionStore) -> None:
    for key, document_type in [("k1", "rfi"), ("k2", "contract"), ("k3", "unknown_needs_review")]:
        store.upsert_inventory_item(
            source_key="sp",
            drive_id="d",
            item_id=key,
            name="raw_" + key,
            web_url="https://x/" + key,
            parent_path="/General",
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
            file_extension="pdf",
            project_key="alpha",
            review_required=True,
            size_class="small",
        )
        store.upsert_document_classification_candidate(
            candidate_id="clf_" + key,
            document_card_id=key,
            document_type=document_type,
            classifier_name="deterministic_v1",
            signal_class="deterministic",
            confidence=0.9,
            confidence_class="deterministic",
            review_required=True,
        )


def test_dry_run_then_apply_then_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = str(tmp_path / "cli.sqlite")
    _seed(ConstructionStore(db))
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )

    result = runner.invoke(app, ["files", "build-document-previews", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files build-document-previews"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["previews"] == 1
    assert payload["guardrails"]["model_invoked"] is False
    assert ConstructionStore(db).count_document_intelligence_previews() == 0

    result = runner.invoke(app, ["files", "build-document-previews", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "apply"
    assert ConstructionStore(db).count_document_intelligence_previews() == 1

    runner.invoke(app, ["files", "build-document-previews", "--apply", "--json"])
    assert ConstructionStore(db).count_document_intelligence_previews() == 1
