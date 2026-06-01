"""Prompt 01A — high-fidelity local PDF extraction (pdfplumber primary, pypdf fallback).

Validates the additive engine upgrade stays within the bounded/redacted dict
contract and never leaves the machine (no upload, no network — pure local libs).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import hb_assistant.files.parsers.pdf as pdf_mod
from hb_assistant.files.parsers.pdf import PDFParser

_FIXTURE = Path(__file__).parent / "fixtures" / "sample_table.pdf"
# A row that only survives if the ruled table is extracted as structured cells.
_STRUCTURED_ROW = "A-300 | Structural Steel"


def test_fixture_exists() -> None:
    assert _FIXTURE.is_file(), "synthetic table PDF fixture missing"


def test_pdfplumber_extracts_structured_table() -> None:
    pytest.importorskip("pdfplumber")
    res = PDFParser().parse(_FIXTURE)
    assert res["extraction_engine"] == "pdfplumber"
    assert res["table_count"] >= 1
    assert res["page_count"] == 1
    # The table is preserved as structured pipe-delimited rows (high fidelity).
    assert "[table]" in res["text_excerpt"]
    assert _STRUCTURED_ROW in res["text_excerpt"]
    # Prose around the table is still captured.
    assert "Project Schedule Summary" in res["text_excerpt"]


def test_bounded_excerpt_never_full_document() -> None:
    """Output is always a bounded excerpt — never the whole file."""
    pytest.importorskip("pdfplumber")
    res = PDFParser().parse(_FIXTURE, max_chars=120)
    assert res["char_count"] <= 120
    assert len(res["text_excerpt"]) <= 120


def test_idempotent_same_bytes_same_output() -> None:
    pytest.importorskip("pdfplumber")
    a = PDFParser().parse(_FIXTURE)
    b = PDFParser().parse(_FIXTURE)
    assert a["text_excerpt"] == b["text_excerpt"]
    assert a["table_count"] == b["table_count"]
    assert a["char_count"] == b["char_count"]


def test_falls_back_to_pypdf_when_pdfplumber_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """With pdfplumber unavailable the parser preserves the original pypdf behavior
    and the same dict contract (no tables, flattened text)."""
    monkeypatch.setattr(pdf_mod, "_pdfplumber", None)
    res = PDFParser().parse(_FIXTURE)
    assert res["extraction_engine"] == "pypdf_fallback"
    assert "text_excerpt" in res and "char_count" in res and "page_count" in res
    assert res["char_count"] > 0
    # pypdf yields flattened text with no structured-table markers.
    assert "table_count" not in res
    assert "[table]" not in res["text_excerpt"]


def test_pdfplumber_beats_pypdf_on_table_fidelity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Measured-improvement guard: the structured table row survives under
    pdfplumber but not under the pypdf fallback."""
    pytest.importorskip("pdfplumber")
    primary = PDFParser().parse(_FIXTURE)
    monkeypatch.setattr(pdf_mod, "_pdfplumber", None)
    fallback = PDFParser().parse(_FIXTURE)
    assert _STRUCTURED_ROW in primary["text_excerpt"]
    assert _STRUCTURED_ROW not in fallback["text_excerpt"]
    assert primary.get("table_count", 0) >= 1


def test_missing_file_is_isolated_failure(tmp_path: Path) -> None:
    """Errors are isolated into the dict contract, not raised."""
    res = PDFParser().parse(tmp_path / "nope.pdf")
    assert res["text_excerpt"] == ""
    assert res["char_count"] == 0
    assert res.get("failure_code") in ("parser_error", "encrypted_or_password_protected")


def test_non_pdf_bytes_fall_through_to_failure(tmp_path: Path) -> None:
    """A non-PDF file must not crash and must not leak content."""
    bogus = tmp_path / "not_a.pdf"
    bogus.write_bytes(b"this is not a pdf at all")
    res = PDFParser().parse(bogus)
    assert res["char_count"] == 0
    assert res["text_excerpt"] == ""
    assert "failure_code" in res
