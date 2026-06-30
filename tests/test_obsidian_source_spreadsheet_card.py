"""A1.11 — spreadsheet card rendering + card-basis line; bounded, no formula/macro execution."""

from __future__ import annotations

from hb_assistant.obsidian_mcp import source_notes
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig


def _config() -> ObsidianMcpConfig:
    return ObsidianMcpConfig.model_validate({"enabled": True})


def _detail(rel: str, ext: str, text: str, **extra):
    base = {
        "source_id": "s1", "source_kind": "external_file", "rel_path": rel, "file_ext": ext,
        "text_excerpt": text, "content_sha256": "abc", "indexed_at": "2026-06-29", "mtime_ns": 1,
    }
    base.update(extra)
    return base


def test_high_value_spreadsheet_card_has_sections_and_basis():
    detail = _detail(
        "25-244/Cost/Cost Report June.xlsx", "xlsx",
        "--- Summary ---\nProject | Cost | Budget\nTotal | 1000 | 1200\n--- Detail ---\nLine | Amount",
        sheet_count=2, project_number="25-244",
    )
    md = source_notes._render_card(_config(), detail, "2026-06-29T00:00:00Z")
    assert "- Card basis: spreadsheet metadata + bounded cell sample" in md
    for section in ("## Spreadsheet Identity", "## PM Relevance",
                    "## Detected Workbook Signals", "## Review / Verification Notes"):
        assert section in md
    assert "cost_report" in md  # high-value class surfaced (cost-report split from project_controls)
    assert "Sheet names: Summary, Detail" in md
    assert "no formulas evaluated, no macros executed" in md


def test_generic_spreadsheet_card_labels_no_high_value_class():
    detail = _detail("25-244/Misc/Tracker.xlsx", "xlsx", "--- Sheet1 ---\nA | B", sheet_count=1)
    md = source_notes._render_card(_config(), detail, "2026-06-29T00:00:00Z")
    assert "## Spreadsheet Identity" in md
    assert "no high-value class detected" in md


def test_card_basis_for_full_text_vs_metadata():
    full = source_notes._card_basis(_detail("a/Plan.pdf", "pdf", "lots of text"))
    assert full == "full extracted text (bounded)"
    nometa = source_notes._card_basis(
        {"file_ext": "pdf", "text_excerpt": "", "extraction_status": "unsupported"}
    )
    assert "filename/path analysis" in nometa


def test_xlsx_parser_is_bounded_and_macro_safe():
    # Repo-truth guard: the parser opens workbooks data_only + read_only (no formula eval, no macros).
    import inspect

    from hb_assistant.files.parsers.xlsx import XLSXParser

    src = inspect.getsource(XLSXParser)
    assert "data_only=True" in src and "read_only=True" in src
    assert XLSXParser.MAX_ROWS_PER_SHEET <= 100 and XLSXParser.MAX_COLS <= 50
