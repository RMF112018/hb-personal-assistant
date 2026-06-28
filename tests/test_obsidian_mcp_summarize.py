"""Vault intelligence (summarize) tools for the UI-managed Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import (
    ObsidianMcpConfigPatch,
    apply_patch,
    load_config,
)
from hb_assistant.obsidian_mcp.mutations import recent_read_receipts
from hb_assistant.obsidian_mcp.summarize import summarize_folder, summarize_note
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

_NOTE = """---
tags: [project, tropical]
---
# Tropical Schedule Review

The owner approved the revised milestone dates. We decided to resequence the
slab pours. Please confirm the crane delivery by Friday. See [[Tropical MOC]].

## Risks

- [ ] Submit RFI 142 for the canopy detail
- Long-lead switchgear is a schedule risk
"""


def _write_config(tmp_path: Path, vault: Path) -> Path:
    app_support = tmp_path / "app-support"
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        "\n".join(
            [
                "paths:",
                f"  application_support_root: {app_support.as_posix()!r}",
                f"  obsidian_vault: {vault.as_posix()!r}",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def _setup(tmp_path, monkeypatch, *, backend="deterministic"):
    vault = tmp_path / "vault"
    (vault / "Work").mkdir(parents=True)
    (vault / "Work" / "Tropical.md").write_text(_NOTE, encoding="utf-8")
    (vault / "Work" / "Notes.md").write_text(
        "# Notes\n\nPlease send the budget. We agreed to proceed with vendor A.\n",
        encoding="utf-8",
    )
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "app.md").write_text("# sys\n", encoding="utf-8")

    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    apply_patch(ObsidianMcpConfigPatch(summarization_backend=backend))
    return load_config(), vault


class _FakeBackend:
    """Injectable GenerationBackend that returns canned JSON (or simulates failure)."""

    def __init__(self, *, payload=None, fail=False):
        self._payload = payload or {}
        self._fail = fail

    def generate_json(self, *, system: str, prompt: str) -> str:
        if self._fail:
            raise RuntimeError("ollama_unavailable")
        return json.dumps(self._payload)


# ---------------------------------------------------------------------------
# Deterministic path
# ---------------------------------------------------------------------------
def test_summarize_note_deterministic(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = summarize_note(config, path="Work/Tropical.md")
    assert result["mode"] == "deterministic_fallback"
    assert result["title"] == "Tropical Schedule Review"
    assert result["summary"]
    assert any("crane" in a.lower() or "rfi" in a.lower() for a in result["action_items"])
    assert any("approved" in d.lower() or "decided" in d.lower() for d in result["decisions"])
    assert "Tropical MOC" in result["suggested_links"]
    assert "project" in result["suggested_tags"]


def test_summarize_note_respects_max_chars(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = summarize_note(config, path="Work/Tropical.md", max_chars=40)
    assert len(result["summary"]) <= 40


# ---------------------------------------------------------------------------
# LLM path + fallback
# ---------------------------------------------------------------------------
def test_summarize_note_uses_injected_llm(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, backend="llm")
    backend = _FakeBackend(
        payload={
            "summary": "LLM executive summary.",
            "key_points": ["point one"],
            "action_items": ["confirm crane"],
            "decisions": ["resequence pours"],
            "entities": ["Tropical"],
            "suggested_tags": ["schedule"],
            "suggested_links": ["Tropical MOC"],
        }
    )
    result = summarize_note(config, path="Work/Tropical.md", backend=backend)
    assert result["mode"] == "llm"
    assert result["summary"] == "LLM executive summary."
    assert result["key_points"] == ["point one"]


def test_summarize_note_falls_back_when_llm_unavailable(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, backend="llm")
    result = summarize_note(config, path="Work/Tropical.md", backend=_FakeBackend(fail=True))
    assert result["mode"] == "deterministic_fallback"
    assert result["title"] == "Tropical Schedule Review"


# ---------------------------------------------------------------------------
# Path hardening
# ---------------------------------------------------------------------------
def test_summarize_note_blocks_protected_path(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError) as exc:
        summarize_note(config, path=".obsidian/app.md", operator_mode=False)
    assert exc.value.code == "protected_path_blocked"


# ---------------------------------------------------------------------------
# Folder summarize
# ---------------------------------------------------------------------------
def test_summarize_folder_aggregates_and_caps(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = summarize_folder(config, root_path="Work", max_files=1, principal_kind="oauth")
    assert result["files_summarized"] == 1
    assert result["truncated"] is True
    assert "themes" in result
    assert result["file_summaries"][0]["path"].startswith("Work/")
    # The folder crawl wrote a redacted bulk-read receipt.
    receipts = recent_read_receipts(5)
    assert receipts[-1]["tool_name"] == "vault_summarize_folder"
    assert receipts[-1]["principal_kind"] == "oauth"


def test_summarize_folder_excludes_protected(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = summarize_folder(config, root_path="", max_files=50)
    paths = {f["path"] for f in result["file_summaries"]}
    assert not any(p.startswith(".obsidian") for p in paths)
    assert "Work/Tropical.md" in paths
