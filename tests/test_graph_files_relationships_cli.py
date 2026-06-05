"""Phase 07C Prompt 08 — `graph files build-document-relationships` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.store.procore_repositories import (
    record_sync_run_start,
    upsert_procore_live_record,
)

runner = CliRunner()


def _seed(store: ConstructionStore, db: str) -> None:
    for key, document_type in [("k1", "rfi"), ("k2", "submittal"), ("k3", "drawings")]:
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
        )
        store.upsert_document_classification_candidate(
            candidate_id="clf_" + key,
            document_card_id=key,
            document_type=document_type,
            classifier_name="deterministic_v1",
            signal_class="deterministic",
            confidence=0.9,
            confidence_class="deterministic",
        )
    # Only rfis + submittals present (drawings is unaligned anyway) -> 2 candidates expected.
    for endpoint_id, rid in [("rfis", "1"), ("submittals", "2")]:
        run_id = "run_" + endpoint_id
        record_sync_run_start(
            sync_run_id=run_id,
            endpoint_id=endpoint_id,
            command_endpoint=endpoint_id,
            legacy_endpoint_alias=None,
            project_key="alpha",
            procore_project_id="pp1",
            company_id="co1",
            mode="history",
            started_at_utc="2026-01-01T00:00:00Z",
            db_path=Path(db),
        )
        upsert_procore_live_record(
            project_key="alpha",
            procore_project_id="pp1",
            endpoint_id=endpoint_id,
            procore_record_id=rid,
            parent_procore_id=None,
            normalized_fields={"number": rid},
            review_required=False,
            sensitive_reason=None,
            source_url_redacted=None,
            last_sync_run_id=run_id,
            now_utc="2026-01-01T00:00:00Z",
            db_path=Path(db),
        )


def test_dry_run_then_apply_then_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = str(tmp_path / "cli.sqlite")
    _seed(ConstructionStore(db), db)
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )

    result = runner.invoke(app, ["files", "build-document-relationships", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files build-document-relationships"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["candidates"] == 2
    assert payload["guardrails"]["model_invoked"] is False
    assert ConstructionStore(db).count_document_relationship_candidates() == 0

    result = runner.invoke(app, ["files", "build-document-relationships", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "apply"
    assert ConstructionStore(db).count_document_relationship_candidates() == 2

    runner.invoke(app, ["files", "build-document-relationships", "--apply", "--json"])
    assert ConstructionStore(db).count_document_relationship_candidates() == 2
