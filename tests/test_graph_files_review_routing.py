"""Phase 06 — sensitive-file review routing for SharePoint / OneDrive driveItems.

Covers routing of every construction-sensitive category + low-confidence project
matches into ``construction_review_queue``, idempotency, the dry-run no-write
posture, the no-extraction guarantee (routed items' V18 decision never allows
extraction), the expanded rule seed, and the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.graph.file_review_router import FileReviewRouter
from hb_assistant.construction.policy import ReviewPolicyEvaluator, load_review_rules
from hb_assistant.construction.policy.models import PROTECTED_CATEGORIES
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_SID = "sp_2023projects_23_435_01_tropical_sl"

# (drive_item_id, name, parent_reference_path, expected_category)
_SENSITIVE_FILES = [
    ("c1", "Master Agreement.pdf", "/Contracts", "contract"),
    ("f1", "Invoice 22.pdf", "/General", "financial"),
    ("cl1", "Claim Summary.pdf", "/Claims", "claim"),
    ("n1", "Notice to Proceed.pdf", "/General", "notice"),
    ("i1", "Certificate of Insurance.pdf", "/General", "insurance_bonding"),
    ("m1", "First Aid Log.pdf", "/General", "medical"),
    ("d1", "Arbitration Demand.pdf", "/General", "dispute"),
    ("co1", "Backcharge Notice.pdf", "/General", "cost_impact"),
    ("s1", "Time Extension Request.pdf", "/General", "schedule_impact"),
    ("sf1", "OSHA Incident Report.pdf", "/Safety", "incident"),
]


def _seed(tmp_path: Path) -> ConstructionStore:
    store = ConstructionStore(str(tmp_path / "rr.sqlite"))
    project_registry_to_v5_source_locations(load_source_registry(), store)
    for item_id, name, parent, _cat in _SENSITIVE_FILES:
        store.upsert_drive_item(
            source_id=_SID,
            drive_id="D1",
            drive_item_id=item_id,
            name=name,
            is_file=True,
            file_extension="pdf",
            parent_reference_path=parent,
        )
    # A low-confidence project match with no sensitivity rule firing.
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="lc1",
        name="misc-doc.pdf",
        is_file=True,
        file_extension="pdf",
        parent_reference_path="/General",
    )
    store.update_drive_item_project_match(
        source_id=_SID,
        drive_item_id="lc1",
        match_status="low_confidence",
        review_required=True,
        review_reason="ambiguous project number",
    )
    # Noise that must never be routed: a folder and a deleted file.
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="dir1",
        name="Contracts",
        is_folder=True,
        parent_reference_path="/",
    )
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="del1",
        name="Old Contract.pdf",
        is_file=True,
        deleted=True,
        parent_reference_path="/Contracts",
    )
    return store


def _router(store: ConstructionStore) -> FileReviewRouter:
    return FileReviewRouter(store, ReviewPolicyEvaluator(load_review_rules()))


# --- routing coverage ----------------------------------------------------------


def test_every_sensitive_category_routes(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    [result] = _router(store).route(source_id=_SID, dry_run=False)
    # Folder + deleted file excluded from items_seen.
    assert result.items_seen == len(_SENSITIVE_FILES) + 1  # + the low-confidence file
    for _id, _name, _parent, category in _SENSITIVE_FILES:
        assert result.by_category.get(category, 0) >= 1, category
    queued = {r["classification_label"] for r in store.list_review_queue(source_key=_SID)}
    for _id, _name, _parent, category in _SENSITIVE_FILES:
        assert category in queued, category


def test_low_confidence_match_routes(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    [result] = _router(store).route(source_id=_SID, dry_run=False)
    assert result.low_confidence_routed >= 1
    rows = store.list_review_queue(source_key=_SID)
    low = [r for r in rows if r["classification_label"] == "low_confidence_project_match"]
    assert low and low[0]["item_id"] == "lc1"
    assert low[0]["rule_id"] == "low-confidence-project-match"


# --- idempotency / dry-run -----------------------------------------------------


def test_routing_is_idempotent(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    [first] = _router(store).route(source_id=_SID, dry_run=False)
    count_after_first = store.count_review_queue(source_key=_SID)
    assert first.enqueued == count_after_first and first.skipped_already_open == 0
    [second] = _router(store).route(source_id=_SID, dry_run=False)
    assert store.count_review_queue(source_key=_SID) == count_after_first
    assert second.enqueued == 0 and second.skipped_already_open == count_after_first


def test_dry_run_enqueues_nothing(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    [result] = _router(store).route(source_id=_SID, dry_run=True)
    assert result.mode == "dry_run"
    assert result.matches_found > 0 and result.enqueued == 0
    assert store.count_review_queue(source_key=_SID) == 0


# --- no-extraction guarantee ---------------------------------------------------


def test_routed_files_cannot_extract(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    # V18 decisions for routed sensitive items: review-required, extraction blocked.
    for item_id, _name, _parent, _cat in _SENSITIVE_FILES:
        store.insert_file_ingestion_decision(
            decision_id=f"de-{item_id}",
            source_id=_SID,
            drive_item_id=item_id,
            drive_id="D1",
            project_key="tropical",
            ingestion_disposition="review_required",
            review_required=True,
            extraction_allowed=False,
            download_allowed=False,
        )
    [result] = _router(store).route(source_id=_SID, dry_run=False)
    assert result.extraction_blocked_for_all_routed is True


def test_cross_check_detects_extraction_leak(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    # An inconsistent decision: a routed (contract) item that still allows
    # extraction. The V18 CHECK only forbids review_required=1 AND
    # extraction_allowed=1, so this is the safety net the router reports on.
    store.insert_file_ingestion_decision(
        decision_id="de-c1",
        source_id=_SID,
        drive_item_id="c1",
        drive_id="D1",
        project_key="tropical",
        ingestion_disposition="eligible",
        review_required=False,
        extraction_allowed=True,
        download_allowed=True,
    )
    [result] = _router(store).route(source_id=_SID, dry_run=False)
    assert result.extraction_blocked_for_all_routed is False


# --- rule seed -----------------------------------------------------------------


def test_seed_loads_and_covers_new_categories() -> None:
    rules = load_review_rules()
    labels = {r.classification_label for r in rules.rules}
    assert len(rules.rules) >= 16
    for cat in PROTECTED_CATEGORIES:
        assert cat in labels
    for cat in (
        "claim",
        "notice",
        "insurance_bonding",
        "medical",
        "dispute",
        "cost_impact",
        "schedule_impact",
    ):
        assert cat in labels, cat
    rule_ids = [r.rule_id for r in rules.rules]
    assert len(rule_ids) == len(set(rule_ids))  # unique


# --- CLI -----------------------------------------------------------------------


def test_cli_review_queue_dry_run_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "rr.sqlite")
    _seed(tmp_path)  # creates the db at that path
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )
    result = runner.invoke(app, ["files", "review-queue", "--source", _SID, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files review-queue"
    assert payload["mode"] == "dry_run"
    assert payload["guardrails"]["graph_calls"] == "none"
    assert payload["guardrails"]["queue_idempotent"] is True
    assert payload["guardrails"]["review_routed_cannot_extract"] is True
    assert payload["results"][0]["matches_found"] > 0
