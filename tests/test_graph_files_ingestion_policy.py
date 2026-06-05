"""Phase 06A — file ingestion eligibility policy.

Covers sensitive → review, allowed → eligible, large-file bands, low-confidence,
blocked extension, the DB CHECK (no extraction for review-required), persistence,
and the CLI.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.graph.ingestion_eligibility import IngestionEligibilityEvaluator
from hb_assistant.construction.policy.file_ingestion import load_file_ingestion_policy
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_SID = "sp_2023projects_23_435_01_tropical_sl"  # has folder_policies (07-RFI deep_index, contracts review)
_BIG = 200 * 1024 * 1024  # 200 MiB (> block)
_WARN = 30 * 1024 * 1024  # 30 MiB (warning band)


def _store(tmp_path: Path) -> ConstructionStore:
    s = ConstructionStore(str(tmp_path / "ip.sqlite"))
    project_registry_to_v5_source_locations(load_source_registry(), s)
    return s


def _add(store, item_id, name, path, *, ext=None, size=None):
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D",
        drive_item_id=item_id,
        name=name,
        path=path,
        parent_reference_path=path,
        is_file=True,
        file_extension=ext,
        size_bytes=size,
    )


def _match(store, item_id, status):
    store.update_drive_item_project_match(
        source_id=_SID,
        drive_item_id=item_id,
        project_key="tropical",
        match_confidence=("high" if status == "matched" else "low"),
        match_status=status,
        review_required=(status != "matched"),
    )


def _by_id(rep):
    return {r.drive_item_id: r for r in rep.items}


def test_policy_loads_and_guardrails_locked() -> None:
    p = load_file_ingestion_policy()
    assert p.default_disposition == "metadata_only"
    assert p.block_review_required_extraction is True
    assert "pdf" in p.extension_dispositions.eligible
    assert p.large_file.block_extract_bytes > p.large_file.extract_warning_bytes


def test_sensitive_folder_routes_to_review(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "s1", "agreement.pdf", "/drive/root:/23-435-01/Contracts/Master", ext="pdf")
    _match(store, "s1", "matched")
    r = _by_id(IngestionEligibilityEvaluator(store).evaluate(dry_run=True))["s1"]
    assert r.ingestion_disposition == "review_required"
    assert r.review_required and not r.extraction_allowed
    assert r.review_reason and "contract" in r.review_reason


def test_allowed_rfi_pdf_is_eligible(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "a1", "RFI-001.pdf", "/drive/root:/23-435-01/07-RFI", ext="pdf", size=12345)
    _match(store, "a1", "matched")
    r = _by_id(IngestionEligibilityEvaluator(store).evaluate(dry_run=True))["a1"]
    assert r.ingestion_disposition == "eligible"
    assert r.extraction_allowed and r.download_allowed and not r.review_required


def test_large_file_over_block_is_blocked_too_large(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "lg", "huge.pdf", "/drive/root:/23-435-01/07-RFI", ext="pdf", size=_BIG)
    _match(store, "lg", "matched")
    r = _by_id(IngestionEligibilityEvaluator(store).evaluate(dry_run=True))["lg"]
    assert r.ingestion_disposition == "blocked_too_large" and not r.extraction_allowed


def test_large_file_in_warning_band_needs_manual_approval(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "wn", "big.pdf", "/drive/root:/23-435-01/07-RFI", ext="pdf", size=_WARN)
    _match(store, "wn", "matched")
    r = _by_id(IngestionEligibilityEvaluator(store).evaluate(dry_run=True))["wn"]
    assert r.ingestion_disposition == "manual_approval_required"
    assert r.review_required and not r.extraction_allowed


def test_low_confidence_match_routes_to_review(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "lc", "doc.pdf", "/drive/root:/23-435-01/07-RFI", ext="pdf", size=100)
    _match(store, "lc", "low_confidence")
    r = _by_id(IngestionEligibilityEvaluator(store).evaluate(dry_run=True))["lc"]
    assert r.ingestion_disposition == "low_confidence" and r.review_required


def test_blocked_extension(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "ex", "tool.exe", "/drive/root:/23-435-01/07-RFI", ext="exe", size=100)
    _match(store, "ex", "matched")
    r = _by_id(IngestionEligibilityEvaluator(store).evaluate(dry_run=True))["ex"]
    assert r.ingestion_disposition == "blocked_unsupported_type" and not r.extraction_allowed


def test_native_extension_is_metadata_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "cad", "model.dwg", "/drive/root:/23-435-01/16-DrawSpecPic", ext="dwg", size=100)
    _match(store, "cad", "matched")
    r = _by_id(IngestionEligibilityEvaluator(store).evaluate(dry_run=True))["cad"]
    assert r.ingestion_disposition == "metadata_only" and not r.extraction_allowed


# --- persistence + CHECK -------------------------------------------------------


def test_dry_run_persists_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "a1", "RFI-001.pdf", "/drive/root:/23-435-01/07-RFI", ext="pdf")
    _match(store, "a1", "matched")
    IngestionEligibilityEvaluator(store).evaluate(dry_run=True)
    assert store.list_file_ingestion_decisions() == []


def test_apply_persists_decisions(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "a1", "RFI-001.pdf", "/drive/root:/23-435-01/07-RFI", ext="pdf", size=10)
    _match(store, "a1", "matched")
    _add(store, "s1", "agreement.pdf", "/drive/root:/23-435-01/Contracts", ext="pdf")
    _match(store, "s1", "matched")
    IngestionEligibilityEvaluator(store).evaluate(dry_run=False)
    decisions = {d["drive_item_id"]: d for d in store.list_file_ingestion_decisions()}
    assert decisions["a1"]["ingestion_disposition"] == "eligible"
    assert decisions["a1"]["extraction_allowed"] is True
    assert decisions["s1"]["review_required"] is True
    assert decisions["s1"]["extraction_allowed"] is False


def test_check_blocks_review_required_extraction(tmp_path: Path) -> None:
    store = _store(tmp_path)
    import hb_assistant.store.connection as conn_mod

    conn = conn_mod.get_connection(str(tmp_path / "ip.sqlite"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO construction_file_ingestion_decisions "
            "(decision_id, source_id, drive_item_id, ingestion_disposition, "
            "review_required, extraction_allowed) VALUES ('x', ?, 'i', 'review_required', 1, 1)",
            (_SID,),
        )


# --- CLI -----------------------------------------------------------------------


def test_cli_ingestion_policy_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "ip.sqlite")
    seed = ConstructionStore(db)
    project_registry_to_v5_source_locations(load_source_registry(), seed)
    seed.upsert_drive_item(
        source_id=_SID,
        drive_id="D",
        drive_item_id="a1",
        name="RFI-001.pdf",
        path="/drive/root:/23-435-01/07-RFI",
        parent_reference_path="/drive/root:/23-435-01/07-RFI",
        is_file=True,
        file_extension="pdf",
        size_bytes=10,
    )
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )
    result = runner.invoke(app, ["files", "ingestion-policy", "--source", _SID, "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output)
    assert payload["command"] == "graph files ingestion-policy"
    assert payload["guardrails"]["block_review_required_extraction"] is True
    assert payload["guardrails"]["graph_calls"] == "none"
