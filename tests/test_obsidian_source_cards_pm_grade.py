"""A1.8 — PM-grade source cards: drawing analyzer, card sections, typed prompt, relationships."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_analyzers
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import (
    DRAWING_PROMPT_VERSION,
    generate_source_card,
    summarize_source,
)
from hb_assistant.store.migrator import SQLiteMigrator

# An A-312-style fixture: representative title-block, revision, section notes, references, datums,
# spaces — NOT a real PDF (text/regex-only, per A1.8 scope; no OCR/render).
A312_TEXT = """YMCA OF THE PALM BEACHES AT LAKE LYTAL PARK
PERMIT DOCUMENTS
WALL SECTIONS
SCALE: 1/2" = 1'-0"
Rev. 1   04-12-24   ADD 01 Bldg Dept Comments

ELEVATION DATUMS
FIRST FLOOR 0'-0"
SECOND FLOOR 14'-0"
ROOF 28'-0"
T.O. PARAPET 30'-8"

ROOMS
CHILD WATCH 105
STEM LAB 128

GENERAL NOTES
1. Provide vapor barrier and waterproofing at all exterior walls.
2. Coordinate exterior ceiling framing with delegated engineer shop drawings.
3. Curtain wall / storefront per A-611. Expansion joints per A-501.

See sheets A-143, A-202, A-501, A-600, A-611 for details.
Built-up SBS roofing at parapet; CMU coordination required.
"""

A312_NAME = "22-101-00/A-312-WALL-SECTIONS-Rev.1.txt"


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
    root_dir = tmp_path / "proj"
    (root_dir / "22-101-00").mkdir(parents=True, exist_ok=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root_dir), "enabled": True}],
    })
    return SourceIndexRepository(db), config, root_dir, vault


def _index(env, name: str, body: str) -> str:
    repo, config, root_dir, _vault = env
    f = root_dir / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return index_source_file(f, config.external_sources[0], repo, config)


class _CapturingBackend:
    """Fake summary backend that records the prompt and returns a valid drawing-schema JSON."""

    def __init__(self) -> None:
        self.prompt: str | None = None
        self.system: str | None = None

    def generate_json(self, *, system: str, prompt: str) -> str:
        self.system, self.prompt = system, prompt
        return json.dumps({
            "plain_english_summary": "Architectural sheet A-312, Wall Sections, for YMCA Lake Lytal.",
            "what_this_sheet_is_for": "Documents exterior wall-section conditions.",
            "scope_elements": ["slab/footing", "CMU", "curtain wall"],
            "coordination_items": ["structural", "waterproofing"],
            "submittals_or_shop_drawings": ["exterior ceiling framing shop drawings"],
            "field_installation_risks": ["expansion joints"],
            "referenced_sheets": ["A-611"],
            "revision_impacts": ["ADD 01 building department comments"],
            "pm_followups": ["coordinate glazing/storefront"],
            "confidence": {"sheet_identity": "high", "scope_summary": "medium", "action_items": "low"},
            "verify_against_source": ["confirm datums against sheet"],
        })


# ----- Slice 2: deterministic analyzer ---------------------------------------------------------

def test_architectural_drawing_analyzer_extracts_title_block_and_refs() -> None:
    a = source_analyzers.from_detail(
        {"rel_path": A312_NAME, "file_ext": "pdf", "text_excerpt": A312_TEXT}
    )
    assert a.document_type == "architectural_drawing"
    assert a.discipline == "architectural"
    assert a.sheet_number == "A-312"
    assert "WALL SECTIONS" in (a.sheet_title or "")
    assert "LAKE LYTAL" in (a.project_name or "")
    assert a.issue_status == "PERMIT DOCUMENTS"
    assert a.revision_number == "1"
    assert a.revision_date == "04/12/24"
    assert "ADD 01" in (a.revision_description or "")
    assert {"A-611", "A-143", "A-202", "A-501", "A-600"} <= set(a.referenced_sheets)
    assert any("vapor barrier" in n.lower() for n in a.numbered_notes)
    assert any("waterproofing" in f for f in a.coordination_flags)
    assert "A-312" not in a.referenced_sheets  # own sheet excluded
    # SCALE line must not be mistaken for an elevation datum.
    assert not any("=" in d for d in a.datums)


def test_general_document_is_not_a_drawing() -> None:
    a = source_analyzers.from_detail(
        {"rel_path": "22-101-00/Meeting Minutes 2024-04.txt", "file_ext": "txt",
         "text_excerpt": "Project meeting minutes. Attendees..."}
    )
    assert a.is_drawing is False
    assert a.document_type in {"meeting_minutes", "general_document"}


# ----- Slice 3: PM-grade card renderer ---------------------------------------------------------

def test_pm_grade_card_has_drawing_sections(env) -> None:
    repo, config, _root, vault = env
    sid = _index(env, A312_NAME, A312_TEXT)
    out = generate_source_card(repo, config, source_id=sid)
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    # Phase 8: drawing facts are folded under Key Facts (no competing top-level Drawing Identity).
    for needle in (
        "## Key Facts", "A-312", "WALL SECTIONS", "ADD 01 Bldg Dept Comments",
        "Referenced sheets:", "A-611", "Coordination flags:", "waterproofing",
        "## Source Basis",
        'document_type: "architectural_drawing"', 'sheet_number: "A-312"',
    ):
        assert needle in card, needle
    assert "## Drawing Identity" not in card


def test_card_does_not_persist_full_body(env) -> None:
    repo, config, _root, vault = env
    # The full body must never be dumped into the card (Phase 8 drops the raw text preview entirely).
    big = A312_TEXT + ("\nEXTRA LINE WITH UNIQUE MARKER ZZZUNIQUE " * 200)
    sid = _index(env, A312_NAME, big)
    out = generate_source_card(repo, config, source_id=sid)
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "ZZZUNIQUE" not in card
    assert "Indexed Text Preview" not in card
    assert len(card) < len(big)


# ----- Slice 4: typed PM-summary prompt --------------------------------------------------------

def test_drawing_summary_prompt_includes_deterministic_facts(env) -> None:
    repo, config, _root, vault = env
    sid = _index(env, A312_NAME, A312_TEXT)
    backend = _CapturingBackend()
    out = summarize_source(repo, config, source_id=sid, backend=backend)
    assert out["summarized"] is True
    assert out["prompt_version"] == DRAWING_PROMPT_VERSION
    # The model input must carry the deterministic facts, not just the raw excerpt.
    prompt = backend.prompt or ""
    for fact in ("DETERMINISTIC FACTS", "A-312", "WALL SECTIONS", "A-611", "Rev", "ADD 01 Bldg Dept Comments"):
        assert fact in prompt, fact
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    # The advisory is folded into the single labelled Advisory Summary section.
    assert "## Advisory Summary" in card
    for needle in ("model-generated, not authoritative", "Architectural sheet A-312",
                   "Coordination items", "PM follow-ups"):
        assert needle in card, needle
    assert repo.get_summary(sid)["prompt_version"] == DRAWING_PROMPT_VERSION


# ----- Slice 5: referenced-sheet relationships -------------------------------------------------

def test_referenced_sheet_links_to_matching_indexed_source(env) -> None:
    repo, config, _root, vault = env
    # Index A-611 in the same project folder so A-312's reference can resolve.
    _index(env, "22-101-00/A-611-CURTAIN-WALL-Rev.0.txt", "Curtain wall details.")
    sid = _index(env, A312_NAME, A312_TEXT)
    # Relationships are resolved at card-generation time (when the full root is indexed).
    out = generate_source_card(repo, config, source_id=sid)
    rels = [r for r in repo.list_relationships(sid)
            if r["relation"] == "links_to" and r["dst_kind"] == "source"]
    assert len(rels) == 1
    assert rels[0]["evidence"]["sheet"] == "A-611"
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    # Resolved referenced-sheet links are surfaced under Key Facts (marked "linked in index").
    assert "A-611-CURTAIN-WALL-Rev.0.txt" in card
    assert "linked in index" in card
    # Unmatched refs are render-only (not written as relationship rows).
    assert "not linked in index" in card


def test_referenced_sheet_match_does_not_cross_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A-611 in a DIFFERENT root must not be matched (conservative same-root matching)."""
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = SourceIndexRepository(db)
    root_a = tmp_path / "rootA"
    root_b = tmp_path / "rootB"
    (root_a / "22-101-00").mkdir(parents=True)
    (root_b / "33-202-00").mkdir(parents=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "writes_enabled": True, "vault_markdown_write_enabled": True,
        "external_sources": [
            {"source_root_key": "a", "path": str(root_a), "enabled": True},
            {"source_root_key": "b", "path": str(root_b), "enabled": True},
        ],
    })
    # A-611 lives only in root B.
    fb = root_b / "33-202-00" / "A-611-CURTAIN-WALL.txt"
    fb.write_text("curtain wall", encoding="utf-8")
    index_source_file(fb, config.external_sources[1], repo, config)
    fa = root_a / "22-101-00" / "A-312-WALL-SECTIONS.txt"
    fa.write_text(A312_TEXT, encoding="utf-8")
    sid = index_source_file(fa, config.external_sources[0], repo, config)
    generate_source_card(repo, config, source_id=sid)  # resolves relationships (same-root only)
    rels = [r for r in repo.list_relationships(sid) if r["relation"] == "links_to"]
    assert rels == []  # never matched across roots


# ----- Identity caution: source_kind + rel_path collision (document current behavior) ----------

def test_same_rel_path_in_two_roots_collides_on_source_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Source identity is keyed on source_kind + rel_path; two roots sharing a rel_path collide.

    This documents CURRENT behavior (A1.8 must not worsen it / must not match relationships across
    roots). A real fix to source identity is a separate follow-up.
    """
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = SourceIndexRepository(db)
    root_a = tmp_path / "rootA"
    root_b = tmp_path / "rootB"
    (root_a / "shared").mkdir(parents=True)
    (root_b / "shared").mkdir(parents=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "external_sources": [
            {"source_root_key": "a", "path": str(root_a), "enabled": True},
            {"source_root_key": "b", "path": str(root_b), "enabled": True},
        ],
    })
    fa = root_a / "shared" / "x.txt"
    fa.write_text("from root A", encoding="utf-8")
    fb = root_b / "shared" / "x.txt"
    fb.write_text("from root B", encoding="utf-8")
    sid_a = index_source_file(fa, config.external_sources[0], repo, config)
    sid_b = index_source_file(fb, config.external_sources[1], repo, config)
    # Current behavior: identical rel_path -> identical source_id (collision); the later write wins.
    assert sid_a == sid_b
    detail = repo.get_source_detail(sid_a)
    assert detail["source_root_key"] == "b"
