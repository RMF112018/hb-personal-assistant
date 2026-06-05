"""Phase 06A — controlled download + bounded extraction.

Covers eligibility gating (only extraction_allowed items), review-required blocking,
explicit download/extract flags, dry-run no-op, cache delete-after-parse + retain,
bounded redacted excerpts (no full text), the DB CHECK guards, and the CLI.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.graph.controlled_extraction import ControlledExtractor
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpError

runner = CliRunner()

_SID = "sp_2023projects_23_435_01_tropical_sl"
_SECRET_EMAIL = "estimator@example.com"
_SECRET_TOKEN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"


class _FakePP:
    """Path policy whose cache dir is an isolated temp dir (no real app-support writes)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def get_cache_dir(self, sub: str = "files") -> Path:
        d = self._root / "cache" / sub
        d.mkdir(parents=True, exist_ok=True)
        return d


def _seed(tmp_path: Path) -> ConstructionStore:
    store = ConstructionStore(str(tmp_path / "ce.sqlite"))
    project_registry_to_v5_source_locations(load_source_registry(), store)
    # Indexed drive items (for the file_extension join).
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="ok1",
        name="RFI-001.txt",
        is_file=True,
        file_extension="txt",
    )
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="rev1",
        name="contract.pdf",
        is_file=True,
        file_extension="pdf",
    )
    # V18 ingestion decisions: one eligible, one review-required.
    store.insert_file_ingestion_decision(
        decision_id="de1",
        source_id=_SID,
        drive_item_id="ok1",
        drive_id="D1",
        project_key="tropical",
        ingestion_disposition="eligible",
        review_required=False,
        extraction_allowed=True,
        download_allowed=True,
    )
    store.insert_file_ingestion_decision(
        decision_id="de2",
        source_id=_SID,
        drive_item_id="rev1",
        drive_id="D1",
        project_key="tropical",
        ingestion_disposition="review_required",
        review_required=True,
        extraction_allowed=False,
        download_allowed=False,
    )
    return store


def _http_writing(content: str) -> MagicMock:
    http = MagicMock()

    def _dl(path, target, *, max_bytes=None, scopes=None):
        Path(target).write_text(content, encoding="utf-8")
        return len(content.encode("utf-8"))

    http.download_to_file.side_effect = _dl
    http.close = MagicMock()
    return http


def _ext(store, tmp_path, http, **kw):
    return ControlledExtractor(http, store, path_policy=_FakePP(tmp_path)).run(_SID, **kw)


def _by_id(rep):
    return {r.drive_item_id: r for r in rep.items}


# --- gating / dry-run ----------------------------------------------------------


def test_dry_run_plan_only_no_side_effects(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    http = _http_writing("x")
    rep = _ext(store, tmp_path, http, dry_run=True, do_download=True, do_extract=True)
    by = _by_id(rep)
    assert by["ok1"].status == "would_extract"
    assert by["rev1"].status == "blocked_review_required"
    http.download_to_file.assert_not_called()
    assert store.list_download_receipts() == []
    assert store.list_file_extraction_runs() == []


def test_review_required_is_blocked_even_on_apply(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    http = _http_writing("data")
    rep = _ext(store, tmp_path, http, dry_run=False, do_download=True, do_extract=True)
    by = _by_id(rep)
    assert by["rev1"].status == "blocked_review_required"
    assert by["rev1"].downloaded is False
    # No receipt/run for the review-required item.
    assert all(r["drive_item_id"] != "rev1" for r in store.list_download_receipts())
    assert all(r["drive_item_id"] != "rev1" for r in store.list_file_extraction_runs())


# --- controlled download + bounded redacted extraction -------------------------


def test_apply_download_extract_eligible_item(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    content = f"RFI body: contact {_SECRET_EMAIL} secret {_SECRET_TOKEN} more text."
    http = _http_writing(content)
    rep = _ext(store, tmp_path, http, dry_run=False, do_download=True, do_extract=True)
    r = _by_id(rep)["ok1"]
    assert r.status == "extracted" and r.downloaded and r.extracted
    assert r.sha256 and r.bytes_written == len(content.encode("utf-8"))
    # bounded + redacted: secrets masked, no full-text leak of the token/email.
    runs = {x["drive_item_id"]: x for x in store.list_file_extraction_runs()}
    excerpt = runs["ok1"]["text_excerpt_redacted"]
    assert _SECRET_EMAIL not in excerpt and _SECRET_TOKEN not in excerpt
    assert "[email-redacted]" in excerpt and "[token-redacted]" in excerpt
    assert runs["ok1"]["full_text_persisted"] is False
    # download receipt + cache deleted after parse.
    rec = {x["drive_item_id"]: x for x in store.list_download_receipts()}
    assert rec["ok1"]["download_completed"] and rec["ok1"]["cache_deleted_after_parse"]
    assert rec["ok1"]["raw_download_url_persisted"] is False
    assert rec["ok1"]["source_file_copied_to_vault"] is False
    # cache file gone.
    assert not (_FakePP(tmp_path).get_cache_dir("files") / "ok1.txt").exists()


def test_apply_download_only_no_extraction_run(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    http = _http_writing("hello")
    _ext(store, tmp_path, http, dry_run=False, do_download=True, do_extract=False)
    assert any(r["drive_item_id"] == "ok1" for r in store.list_download_receipts())
    assert store.list_file_extraction_runs() == []


def test_retain_cache_keeps_file(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    http = _http_writing("keep me")
    rep = _ext(
        store, tmp_path, http, dry_run=False, do_download=True, do_extract=True, retain_cache=True
    )
    assert _by_id(rep)["ok1"].cache_deleted is False
    assert (_FakePP(tmp_path).get_cache_dir("files") / "ok1.txt").exists()


def test_graph_error_is_redacted(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    http = MagicMock()
    http.download_to_file.side_effect = GraphHttpError(
        "GET", "/drives/D1/items/ok1/content", 403, "denied"
    )
    rep = _ext(store, tmp_path, http, dry_run=False, do_download=True, do_extract=True)
    r = _by_id(rep)["ok1"]
    assert r.status == "error" and r.error_redacted == "graph_403"
    assert "denied" not in json.dumps(rep.model_dump())


# --- CHECK guards --------------------------------------------------------------


@pytest.mark.parametrize(
    "col", ["full_text_persisted", "raw_download_url_persisted", "source_file_copied_to_vault"]
)
def test_check_guards_reject_unsafe_values(tmp_path: Path, col: str) -> None:
    _seed(tmp_path)
    import hb_assistant.store.connection as conn_mod

    conn = conn_mod.get_connection(str(tmp_path / "ce.sqlite"))
    if col == "full_text_persisted":
        sql = (
            "INSERT INTO construction_file_extraction_runs "
            "(extraction_id, source_id, drive_item_id, parser_name, parser_version, "
            "extraction_status, full_text_persisted) VALUES ('x', ?, 'i', 'p', 'v', 'ok', 1)"
        )
    else:
        sql = (
            f"INSERT INTO construction_graph_download_receipts "
            f"(receipt_id, source_id, drive_item_id, mode, status, {col}) "
            f"VALUES ('x', ?, 'i', 'apply', 'ok', 1)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, (_SID,))


# --- CLI -----------------------------------------------------------------------


def test_cli_extract_dry_run_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "ce.sqlite")
    _seed(tmp_path)  # creates the db at that path
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )
    result = runner.invoke(app, ["files", "extract", "--source", _SID, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files extract"
    assert payload["mode"] == "dry_run"
    assert payload["guardrails"]["full_text_persisted"] is False
    assert payload["guardrails"]["download_url_cached"] is False
    assert payload["guardrails"]["block_review_required_extraction"] is True
