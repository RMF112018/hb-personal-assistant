"""A1.5 — per-file-type advisory prompts (`llm._prompt_for`) + Phase 8 card-body shape.

Phase 8 removed the deterministic ``## File Analysis`` block (and its ``_analyzer_block`` helper):
file-type/extraction evidence now lives in the Source Summary / Key Facts / Source Basis sections of
the canonical 11-section card. The per-file-type advisory *prompts* are unchanged and still tested.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import llm
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

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


def test_generated_card_uses_template_sections_not_file_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    # Phase 8: deterministic file-type evidence is in Source Summary / Source Basis, not File Analysis.
    assert "## Source Summary" in card and "## Key Facts" in card and "## Source Basis" in card
    assert "## File Analysis" not in card
    # The Markdown extension + extraction facts surface in the Source Summary line.
    assert "Markdown note" in card
