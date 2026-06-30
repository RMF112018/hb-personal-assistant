"""A1.9 — bid_package classification (over RFI), extraction, deterministic card, typed summary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_analyzers
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import (
    BID_PACKAGE_PROMPT_VERSION,
    generate_source_card,
    summarize_source,
)
from hb_assistant.store.migrator import SQLiteMigrator

BID_PATH = ("25-244-01 WLP - Project Documents/10_Preconstruction/Estimating/"
            "05 Bid Packages/Commercial/Section 275 Bid Package 08-03 Glass Windows and Doors.txt")
BID_TEXT = """Bid Package 08-03 Glass Windows & Doors
BID DOCUMENTS
Provide all necessary labor, taxes, materials, tools, equipment, plant, supervision, scaffolding,
supplies, transportation, mobilizations, layout, permits, licenses, fees, services, and all others
incidental work for a complete installation.
Inclusions:
Exterior storefront assemblies, storefront doors, and hardware.
Exterior curtain wall assemblies, break metal, and cladding.
Glazing and related sealants.
Exclusions:
Structural steel supports by others.
"""


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    return SourceIndexRepository(db), config, root, vault


def _index(env, rel: str, body: str) -> str:
    repo, config, root, _vault = env
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return index_source_file(f, config.external_sources[0], repo, config)


class _CapturingBackend:
    def __init__(self) -> None:
        self.prompt: str | None = None

    def generate_json(self, *, system: str, prompt: str) -> str:
        self.prompt = prompt
        return json.dumps({
            "plain_english_summary": "Glass/glazing bid package 08-03 for WLP.",
            "scope_covered": ["storefront", "curtain wall"],
            "included_work": ["storefront assemblies"],
            "excluded_or_unclear_work": ["structural steel by others"],
            "procurement_risks": ["long-lead glazing"],
            "coordination_items": ["structural"],
            "bid_clarifications_needed": ["confirm hardware"],
            "pm_followups": ["coordinate glazing"],
            "confidence": {"package_identity": "high", "scope_summary": "medium", "followups": "low"},
            "verify_against_source": ["confirm package number"],
        })


# ----- analyzer ---------------------------------------------------------------------------------

def test_bid_package_classified_over_rfi() -> None:
    a = source_analyzers.from_detail({"rel_path": BID_PATH, "file_ext": "docx", "text_excerpt": BID_TEXT})
    assert a.document_type == "bid_package"
    assert a.document_type != "rfi"
    assert a.is_drawing is False
    assert a.bid_package_number == "08-03"
    assert "Glass Windows" in (a.bid_package_title or "")
    assert a.issue_status == "BID DOCUMENTS"
    assert {"storefront", "curtain wall", "glazing"} <= set(a.trade_scope)
    assert any("storefront" in i.lower() for i in a.inclusions)
    assert "preconstruction" in a.procurement_signals and "estimating" in a.procurement_signals


def test_true_rfi_still_classifies_as_rfi() -> None:
    a = source_analyzers.from_detail({
        "rel_path": "25-244-01/RFIs/door-hardware.txt", "file_ext": "txt",
        "text_excerpt": "Request for Information RFI #012\nPlease clarify the door hardware schedule.",
    })
    assert a.document_type == "rfi"


def test_doc_mentioning_rfi_is_not_rfi() -> None:
    a = source_analyzers.from_detail({
        "rel_path": "25-244-01/notes/meeting.txt", "file_ext": "txt",
        "text_excerpt": "We will submit rfis later for clarification. General coordination notes.",
    })
    assert a.document_type != "rfi"


# ----- deterministic card -----------------------------------------------------------------------

def test_bid_package_card_renders_pm_sections(env) -> None:
    repo, config, _root, vault = env
    sid = _index(env, BID_PATH, BID_TEXT)
    out = generate_source_card(repo, config, source_id=sid)
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    # Phase 8: bid detail is folded into Key Facts (no competing top-level Bid Package Identity).
    for needle in (
        'document_type: "bid_package"', 'bid_package_number: "08-03"',
        "## Key Facts", "Package number: 08-03", "Inclusions:", "Exclusions:",
        "Trade scope:", "Procurement signals:", "## Source Basis", "storefront",
    ):
        assert needle in card, needle
    assert "## Bid Package Identity" not in card


# ----- typed summary ----------------------------------------------------------------------------

def test_bid_package_typed_summary_prompt_and_render(env) -> None:
    repo, config, _root, vault = env
    sid = _index(env, BID_PATH, BID_TEXT)
    backend = _CapturingBackend()
    out = summarize_source(repo, config, source_id=sid, backend=backend)
    assert out["summarized"] is True
    assert out["prompt_version"] == BID_PACKAGE_PROMPT_VERSION
    prompt = backend.prompt or ""
    for fact in ("DETERMINISTIC FACTS", "08-03", "Glass Windows", "Inclusions", "storefront"):
        assert fact in prompt, fact
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "## Advisory Summary" in card
    for needle in ("model-generated, not authoritative", "Glass/glazing bid package 08-03",
                   "Scope covered", "Procurement risks", "Bid clarifications needed",
                   'summary_prompt_version: "source-card-bid-package-v1"'):
        assert needle in card, needle
    assert repo.get_summary(sid)["prompt_version"] == BID_PACKAGE_PROMPT_VERSION
