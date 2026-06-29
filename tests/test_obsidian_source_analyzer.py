"""A1.5 — file-type analyzer templates (deterministic card body) + per-type advisory prompts.

The deterministic ``_analyzer_block`` derives file-type-specific evidence from existing index
metadata (no model, no file dump; sensitive sources withhold the outline). ``_prompt_for``
selects a file-type-tuned advisory system prompt with the same JSON output contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import llm
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import _analyzer_block, generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator


def _detail(**over: object) -> dict:
    base = {"file_ext": "txt", "rel_path": "a.txt", "source_kind": "external_file",
            "extraction_status": "ok", "text_excerpt": "hello"}
    base.update(over)
    return base


# ----------------------------------------------------------------------------- _analyzer_block


def test_md_outline() -> None:
    block = "\n".join(_analyzer_block(_detail(
        file_ext="md", rel_path="n.md",
        text_excerpt="# Title\n\nintro\n\n## Scope\n\n- a\n\n### Detail\n",
    )))
    assert "File Analysis — Markdown note" in block
    assert "Title" in block and "Scope" in block and "Detail" in block


def test_pdf_text_vs_scanned() -> None:
    text_pdf = "\n".join(_analyzer_block(_detail(file_ext="pdf", rel_path="d.pdf", page_count=12)))
    assert "Pages: 12" in text_pdf
    assert "text-based PDF" in text_pdf

    scanned = "\n".join(_analyzer_block(_detail(
        file_ext="pdf", rel_path="d.pdf", page_count=3, extraction_status="failed", text_excerpt=None,
    )))
    assert "scanned/image-only" in scanned


def test_xlsx_and_docx_and_unknown() -> None:
    xlsx = "\n".join(_analyzer_block(_detail(file_ext="xlsx", rel_path="b.xlsx", sheet_count=4)))
    assert "Excel workbook" in xlsx and "Sheets: 4" in xlsx

    docx = "\n".join(_analyzer_block(_detail(file_ext="docx", rel_path="c.docx", paragraph_count=20)))
    assert "Word document" in docx and "Paragraphs: 20" in docx

    unknown = "\n".join(_analyzer_block(_detail(file_ext="bin", rel_path="x.bin", text_excerpt=None)))
    assert "Binary or unsupported" in unknown


def test_sensitive_source_has_no_outline() -> None:
    # sensitive source: text stored encrypted (text_vault_ref) → no excerpt → no heading outline.
    block = "\n".join(_analyzer_block(_detail(
        file_ext="md", rel_path="s.md", text_excerpt=None, text_vault_ref="vault:123",
    )))
    assert "File Analysis — Markdown note" in block
    assert "Heading outline" not in block


# --------------------------------------------------------------------------------- _prompt_for


def test_prompt_for_selects_by_ext() -> None:
    assert "PDF document" in llm._prompt_for("pdf")
    assert "spreadsheet" in llm._prompt_for("xlsx").lower()
    assert "Word document" in llm._prompt_for("docx")
    # default fallback for unknown / None
    assert llm._prompt_for(None) == llm._SYSTEM_PROMPT
    assert llm._prompt_for("zzz") == llm._SYSTEM_PROMPT


def test_all_prompts_keep_json_contract() -> None:
    for ext in ("pdf", "docx", "xlsx", "csv", "md", "txt"):
        assert "Return ONLY a JSON object" in llm._prompt_for(ext)


# ---------------------------------------------------------------------------------- integration


def test_generated_card_includes_analyzer_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root_dir = tmp_path / "proj"
    (root_dir / "22-101-00").mkdir(parents=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root_dir), "enabled": True}],
    })
    repo = SourceIndexRepository(db)
    f = root_dir / "22-101-00" / "scope.md"
    f.write_text("# Scope\n\nUnderground conduit.\n\n## RFI\n", encoding="utf-8")
    sid = index_source_file(f, config.external_sources[0], repo, config)
    out = generate_source_card(repo, config, source_id=sid, overwrite=False, principal_kind="local")
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "## File Analysis — Markdown note" in card
    assert "Scope" in card
