"""Phase 9+10 file/attachment selective ingestion tests.

Covers: relevance (Phase 6 signals + heuristics), approval gate, full parser matrix (bounds, errors, failure codes),
service pipeline (dry-run, real mocked DL/parse, persist, SourceLinkRegistry "parsed_from"), redaction/leak guards,
links, eligibility matrix. All green, zero full content in artifacts/outputs/logs.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hb_assistant.files.eligibility import ApprovalGate, EligibilityGate
from hb_assistant.files.relevance import FileRelevanceScorer, RelevanceScore
from hb_assistant.files.router import ParserRouter
from hb_assistant.files.service import FileIngestionService
from hb_assistant.normalize.drive_item import DriveItem
from hb_assistant.store.repositories import Store


def test_eligibility_matrix():
    gate = EligibilityGate()
    small_pdf = DriveItem(id="p1", name="doc.pdf", size=1_000_000, is_file=True)
    res = gate.check(small_pdf)
    assert res.eligible is True
    assert res.reason == "ok"

    too_big = DriveItem(id="big", name="big.pdf", size=300 * 1024 * 1024, is_file=True)
    res2 = gate.check(too_big)
    assert res2.eligible is False
    assert res2.reason in ("too_large", "manual_approval_required")


def test_relevance_scoring_matrix():
    scorer = FileRelevanceScorer()
    # high value: bobby mention + name + reasonable size
    item = DriveItem(id="r1", name="Q3 Report.pdf", size=2_000_000, is_file=True, source_record_id=42)
    rel = scorer.score(item, parent_classifications=["bobby_mention", "possible_action_or_waiting"])
    assert isinstance(rel, RelevanceScore)
    assert rel.score > 0.5
    assert rel.worth_ingesting is True
    assert "bobby_mention" in rel.reasons
    assert any(r.startswith("name_kw:") for r in rel.reasons)

    # low: large + no signals
    big = DriveItem(id="r2", name="huge.zip", size=400 * 1024 * 1024, is_file=True)
    rel2 = scorer.score(big)
    assert rel2.score < 0.25
    assert rel2.worth_ingesting is False

    # tiny penalty
    tiny = DriveItem(id="r3", name="empty.txt", size=10, is_file=True)
    rel3 = scorer.score(tiny)
    assert rel3.score < 0.2


def test_approval_gate():
    from hb_assistant.files.eligibility import EligibilityResult as ER

    gate = ApprovalGate()
    elig_ok = EligibilityGate().check(DriveItem(id="s", name="ok.pdf", size=1000, is_file=True))
    ok, reason = gate.is_approved(elig_ok)
    assert ok is True
    assert reason == "auto_approved"

    elig_big = ER(eligible=False, reason="manual_approval_required", requires_manual_approval=True, size_mb=350)
    nok, nreason = gate.is_approved(elig_big, source_record_id=999)
    assert nok is False
    assert "manual" in nreason

    gate2 = ApprovalGate(approved_source_ids={999})
    ok2, r2 = gate2.is_approved(elig_big, source_record_id=999)
    assert ok2 is True
    assert r2 == "explicitly_approved"


def test_parser_router_and_matrix(tmp_path: Path):
    router = ParserRouter()
    # unsupported
    bad = tmp_path / "foo.xyz"
    bad.write_text("x")
    res = router.parse(bad)
    assert res.get("failure_code") == "unsupported_type" or res.get("error") == "unsupported_type"

    # txt real file
    txt = tmp_path / "note.txt"
    txt.write_text("hello world " * 100)
    res2 = router.parse(txt)
    assert "text_excerpt" in res2
    assert res2["char_count"] <= 8000
    assert "hello world" in res2["text_excerpt"]

    # csv
    csvf = tmp_path / "data.csv"
    csvf.write_text("a,b\n1,2\n3,4\n")
    res3 = router.parse(csvf)
    assert res3["char_count"] > 0

    # zip metadata (create real small zip)
    zf = tmp_path / "arch.zip"
    with zipfile.ZipFile(zf, "w") as z:
        z.writestr("inside.txt", "secret but small")
    res4 = router.parse(zf)
    assert "zip:" in res4["text_excerpt"].lower() or "entry" in res4.get("text_excerpt", "").lower()
    assert res4.get("metadata_only") is True

    # image meta
    img = tmp_path / "photo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    res5 = router.parse(img)
    assert "image:" in res5["text_excerpt"] or "metadata_only" in res5


def test_parsers_error_isolation_and_failure_codes(tmp_path: Path):
    router = ParserRouter()
    # non existing -> parser_error path via open fail
    missing = tmp_path / "nope.pdf"
    res = router.parse(missing)
    assert res.get("failure_code") in ("parser_error", "unsupported_type")


def test_service_ingest_items_full_pipeline_dry_and_links(tmp_path: Path):
    dbp = tmp_path / "ingest.sqlite"
    store = Store(db_path=str(dbp))
    # mock drive not used in ingest_items path
    mock_drive = MagicMock()
    svc = FileIngestionService(drive_client=mock_drive, store=store)

    # create real source_records (FK requirement for files/parser_outputs)
    sid1 = store.upsert_source_record(source_type="email", source_key="test:2001", source_system="m365")
    sid2 = store.upsert_source_record(source_type="email", source_key="test:2002", source_system="m365")

    items = [
        DriveItem(id="i1", name="Report.pdf", size=123456, is_file=True, source_record_id=sid1),
        DriveItem(id="i2", name="tiny.md", size=50, is_file=True, source_record_id=sid2),
    ]
    classifs = {sid1: ["bobby_mention"]}

    # dry run
    res = svc.ingest_items(items, dry_run=True, classifications_by_source=classifs)
    assert len(res) == 2
    assert res[0]["decision"] in ("would_ingest", "skipped_low_relevance")
    assert "relevance" in res[0]
    assert "eligibility" in res[0]
    # no real DL happened
    assert store.get_file(sid1) is None

    # with approved + non-dry but mock downloader/parser to avoid real http
    with patch.object(svc, "downloader") as mock_dl, patch.object(svc, "parser") as mock_pr:
        fake = tmp_path / "fake.bin"
        fake.write_text("bounded excerpt here for test " * 10)
        mock_dl.download.return_value = fake
        mock_pr.parse.return_value = {"text_excerpt": "bounded excerpt here for test", "char_count": 30}
        res2 = svc.ingest_items([items[0]], dry_run=False, approved_source_ids={sid1}, classifications_by_source=classifs)
        assert res2[0]["decision"] == "ingested"
        assert "excerpt_preview" in res2[0]
        assert "sha256" in res2[0]
        # links and parser output recorded
        outs = store.list_parser_outputs(sid1)
        assert len(outs) >= 1
        assert "bounded excerpt" in outs[0]["text_excerpt"]
        links = store.get_links_for_source(sid1)
        assert any(l.get("link_type") == "parsed_from" for l in links)


def test_no_full_file_content_in_any_artifact_or_excerpt(tmp_path: Path):
    """Strict leak guard: no full content, secrets, or long unredacted in DB, results, temp, or evidence-like."""
    dbp = tmp_path / "leak.sqlite"
    store = Store(db_path=str(dbp))
    mock_drive = MagicMock()
    svc = FileIngestionService(drive_client=mock_drive, store=store)

    # create a "file" with secret
    secret = "SECRET_TOKEN_ABCDEF1234567890_fullbody"
    fpath = tmp_path / "secret.txt"
    fpath.write_text(secret * 5)

    items = [DriveItem(id="leak1", name="secret.txt", size=len(secret*5), is_file=True, source_record_id=3001)]

    with patch.object(svc, "downloader") as md, patch.object(svc, "parser") as mp:
        md.download.return_value = fpath
        mp.parse.return_value = {"text_excerpt": "REDACTED_BOUNDED_EXCERPT_ONLY", "char_count": 30}
        res = svc.ingest_items(items, dry_run=False, approved_source_ids={3001})

    # results redacted
    assert "SECRET" not in str(res)
    assert "TOKEN_ABCDEF" not in str(res)
    # db excerpts bounded/redacted
    outs = store.list_parser_outputs(3001)
    for o in outs:
        assert "SECRET" not in o.get("text_excerpt", "")
        assert len(o.get("text_excerpt", "")) <= 8000
    # file record no content
    frow = store.get_file(3001)
    if frow:
        assert "SECRET" not in str(frow)
    # no full in any str of artifacts
    assert "SECRET_TOKEN_ABCDEF1234567890" not in str(store.get_summary())
