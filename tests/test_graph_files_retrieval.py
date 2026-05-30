"""Phase 06A Prompt 14 — source-linked retrieval over bounded file excerpts.

Covers ranked retrieval with source traceability (drive item / web URL / project /
parser output / processing receipt), bounded redacted excerpts only, project &
source scoping, exclusion of review-routed / sensitive files, and the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.graph.file_retrieval import FileRetriever
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_SID = "sp_2023projects_23_435_01_tropical_sl"
# A second source belonging to a different project (for scope tests).
_OTHER_SID = "sp_2022projects_22_112_01_pga_the_modern_garage"
_OTHER_PROJECT = "pga-modern-garage"

_RFI_EXCERPT = (
    "RFI-012 submittal review: meeting minutes note the structural shop drawings are due. "
    "Contact [email-redacted] regarding the [token-redacted] approval."
)


def _seed(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    project_registry_to_v5_source_locations(load_source_registry(), store)

    # Matching, eligible, extracted RFI doc in the tropical project.
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="rfi1",
        name="RFI-012 Submittal.pdf",
        is_file=True,
        file_extension="pdf",
        parent_reference_path="/RFIs",
        web_url="https://hedrickbrothers.sharepoint.com/sites/tropical/RFI-012.pdf",
    )
    store.insert_file_ingestion_decision(
        decision_id="d1",
        source_id=_SID,
        drive_item_id="rfi1",
        drive_id="D1",
        project_key="tropical",
        ingestion_disposition="eligible",
        review_required=False,
        extraction_allowed=True,
        download_allowed=True,
    )
    store.insert_download_receipt(
        receipt_id="rcpt1",
        source_id=_SID,
        drive_item_id="rfi1",
        drive_id="D1",
        project_key="tropical",
        mode="apply",
        download_attempted=True,
        download_completed=True,
        cache_deleted_after_parse=True,
        status="downloaded",
    )
    store.insert_file_extraction_run(
        extraction_id="ext1",
        source_id=_SID,
        drive_item_id="rfi1",
        drive_id="D1",
        project_key="tropical",
        parser_name="files-router",
        parser_version="files-router-1",
        content_hash="h1",
        extraction_status="ok",
        text_excerpt_redacted=_RFI_EXCERPT,
        char_count=len(_RFI_EXCERPT),
        review_required=False,
    )

    # Non-matching extracted doc (no query terms).
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="misc1",
        name="Site Photo Log.pdf",
        is_file=True,
        file_extension="pdf",
        parent_reference_path="/Photos",
    )
    store.insert_file_extraction_run(
        extraction_id="ext2",
        source_id=_SID,
        drive_item_id="misc1",
        drive_id="D1",
        project_key="tropical",
        parser_name="files-router",
        parser_version="files-router-1",
        extraction_status="ok",
        text_excerpt_redacted="weekly site photo index and weather notes",
        char_count=42,
        review_required=False,
    )

    # A review-required extraction run (must never be retrieved).
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="sens1",
        name="RFI Settlement Contract.pdf",
        is_file=True,
        file_extension="pdf",
        parent_reference_path="/Contracts",
    )
    store.insert_file_extraction_run(
        extraction_id="ext3",
        source_id=_SID,
        drive_item_id="sens1",
        drive_id="D1",
        project_key="tropical",
        parser_name="files-router",
        parser_version="files-router-1",
        extraction_status="ok",
        text_excerpt_redacted="RFI submittal settlement contract terms",
        char_count=39,
        review_required=True,
    )

    # A second-project extracted doc (for project scoping).
    store.upsert_drive_item(
        source_id=_OTHER_SID,
        drive_id="D2",
        drive_item_id="rfi2",
        name="RFI Submittal Garage.pdf",
        is_file=True,
        file_extension="pdf",
        parent_reference_path="/RFIs",
    )
    store.insert_file_extraction_run(
        extraction_id="ext4",
        source_id=_OTHER_SID,
        drive_item_id="rfi2",
        drive_id="D2",
        project_key=_OTHER_PROJECT,
        parser_name="files-router",
        parser_version="files-router-1",
        extraction_status="ok",
        text_excerpt_redacted="RFI submittal meeting minutes for the garage",
        char_count=44,
        review_required=False,
    )
    return store


_QUERY = "RFI submittal meeting minutes"


def test_retrieval_returns_source_linked_hit(tmp_path: Path) -> None:
    store = _seed(str(tmp_path / "db.sqlite"))
    report = FileRetriever(store).retrieve(query=_QUERY, project_key="tropical")
    assert report.ok and report.hit_count >= 1
    top = report.hits[0]
    assert top.drive_item_id == "rfi1"
    assert top.project_key == "tropical"
    assert top.web_url and top.web_url.startswith("https://")
    assert top.parser_output_id == "ext1"  # parser output id == extraction id
    assert top.processing_receipt_id == "rcpt1"  # processing-receipt link
    assert top.score > 0.0


def test_excerpt_is_bounded_and_redacted(tmp_path: Path) -> None:
    store = _seed(str(tmp_path / "db.sqlite"))
    report = FileRetriever(store).retrieve(query=_QUERY, project_key="tropical")
    top = report.hits[0]
    assert len(top.excerpt_redacted) <= 2000
    assert top.excerpt_redacted == _RFI_EXCERPT  # bounded redacted excerpt preserved
    assert "[email-redacted]" in top.excerpt_redacted
    assert "[token-redacted]" in top.excerpt_redacted
    # No full-text marker, no raw delta link in any returned excerpt.
    blob = json.dumps(report.model_dump())
    assert "full_document_text" not in blob and "deltatoken=" not in blob


def test_project_and_source_scoping(tmp_path: Path) -> None:
    store = _seed(str(tmp_path / "db.sqlite"))
    rt = FileRetriever(store)
    tropical = rt.retrieve(query=_QUERY, project_key="tropical")
    assert {h.drive_item_id for h in tropical.hits} == {"rfi1"}  # other project excluded
    other = rt.retrieve(query=_QUERY, project_key=_OTHER_PROJECT)
    assert {h.drive_item_id for h in other.hits} == {"rfi2"}
    scoped = rt.retrieve(query=_QUERY, source_id=_OTHER_SID)
    assert all(h.source_id == _OTHER_SID for h in scoped.hits)


def test_review_routed_files_excluded(tmp_path: Path) -> None:
    store = _seed(str(tmp_path / "db.sqlite"))
    # Also place an otherwise-matching item into the open review queue.
    from hb_assistant.construction.policy.models import RuleMatch

    store.enqueue_review_item(
        RuleMatch(
            rule_id="folder-contracts",
            item_id="misc1",
            source_key=_SID,
            project_key="tropical",
            name="Site Photo Log.pdf",
            parent_path="/Photos",
            sensitivity="high",
            classification_label="contract",
            reason="seeded",
            suggested_action="controller_review",
        )
    )
    report = FileRetriever(store).retrieve(query="RFI submittal settlement", project_key="tropical")
    ids = {h.drive_item_id for h in report.hits}
    assert "sens1" not in ids  # review_required extraction run excluded
    assert "misc1" not in ids  # open review-queue item excluded
    assert report.review_routed_excluded >= 1


def test_no_match_returns_empty(tmp_path: Path) -> None:
    store = _seed(str(tmp_path / "db.sqlite"))
    report = FileRetriever(store).retrieve(query="helicopter zoology", project_key="tropical")
    assert report.ok and report.hit_count == 0 and report.hits == []


def test_cli_retrieve_offline(tmp_path: Path, monkeypatch) -> None:
    db = str(tmp_path / "db.sqlite")
    _seed(db)
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )
    result = runner.invoke(
        app, ["files", "retrieve", "--project", "tropical", "--query", _QUERY, "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files retrieve"
    assert payload["ok"] is True
    assert payload["result"]["hit_count"] >= 1
    assert payload["guardrails"]["full_text_persisted"] is False
    assert payload["guardrails"]["review_routed_excluded"] is True
