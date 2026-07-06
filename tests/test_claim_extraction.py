"""N8C-4 — rule-based claim extraction + N8C-2/N8C-3-gated card extraction.

Deterministic extraction (no LLM). The card-aware orchestrator blocks on ambiguous/deleted sources,
labels stale-source extraction, pulls content only via the bounded navigation service, and never runs
on its own.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import claim_extraction as ce
from hb_assistant.obsidian_mcp.claim_models import EVIDENCE_MAX_CHARS
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

CLAIM_TEXT = (
    "We decided to keep MCP read-only.\n"
    "Risk: switchgear delivery may slip.\n"
    "Warranty expires March 4, 2027.\n"
    "I prefer 65 percent hydration.\n"
    "Assumption: NAS remains the canonical host.\n"
    "I will send the revised schedule.\n"
    "Action: follow up due by Friday.\n"
)
REL_A = "docs/claims.txt"
REL_B = "docs/other.txt"


# --- pure extractor rules --------------------------------------------------------------
def test_each_claim_type_extracted() -> None:
    got = {c.claim_type for c in ce.extract_claims_from_text(CLAIM_TEXT)}
    assert {"decision_candidate", "risk", "date", "preference", "assumption",
            "commitment", "task_candidate"} <= got


@pytest.mark.parametrize("text,expected", [
    ("we decided to keep MCP read-only", "decision_candidate"),
    ("risk: switchgear delivery may slip", "risk"),
    ("warranty expires March 4, 2027", "date"),
    ("I prefer 65 percent hydration", "preference"),
    ("assumption: NAS remains canonical host", "assumption"),
    ("I will send the revised schedule", "commitment"),
    ("due by Friday", "task_candidate"),
])
def test_single_rule_maps(text: str, expected: str) -> None:
    assert expected in [c.claim_type for c in ce.extract_claims_from_text(text)]


def test_extraction_is_deterministic() -> None:
    a = ce.extract_claims_from_text(CLAIM_TEXT)
    b = ce.extract_claims_from_text(CLAIM_TEXT)
    assert [(c.claim_type, c.claim_text) for c in a] == [(c.claim_type, c.claim_text) for c in b]


def test_evidence_excerpts_bounded() -> None:
    huge = "risk: " + ("y " * 5000)
    for c in ce.extract_claims_from_text(huge):
        assert len(c.evidence_excerpt) <= 400  # segment cap; repo bounds further to EVIDENCE_MAX_CHARS
    assert EVIDENCE_MAX_CHARS >= 400


# --- card-aware orchestrator (N8C-2 + N8C-3 gated) -------------------------------------
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
    repo = SourceIndexRepository(db)
    (root / "docs").mkdir(parents=True)
    (root / REL_A).write_text(CLAIM_TEXT, encoding="utf-8")
    (root / REL_B).write_text("nothing here", encoding="utf-8")
    sid_a = index_source_file(root / REL_A, config.external_sources[0], repo, config)
    sid_b = index_source_file(root / REL_B, config.external_sources[0], repo, config)
    card_a = generate_source_card(repo, config, source_id=sid_a)["note_path"]
    generate_source_card(repo, config, source_id=sid_b)
    return {"source_repo": repo, "claim_repo": ClaimRepository(db), "config": config, "db": db,
            "sid_a": sid_a, "sid_b": sid_b, "card_a": card_a}


def test_no_claims_until_explicit_call(env) -> None:
    # Fixture indexed + generated cards but ran NO extraction; claims table stays empty.
    assert env["claim_repo"].count_claims() == 0


def test_extract_for_card_links_and_labels(env) -> None:
    res = ce.extract_claims_for_card(env["claim_repo"], env["source_repo"], env["config"],
                                     env["sid_a"], env["card_a"])
    assert res["count"] > 0 and res["blocked"] is False and res["source_state"] == "current"
    claims = env["claim_repo"].get_claims_for_source(env["sid_a"])
    assert claims
    types = {c["claim_type"] for c in claims}
    assert {"decision_candidate", "risk"} & types
    for c in claims:
        assert c["source_id"] == env["sid_a"]
        assert c["note_rel_path"] == env["card_a"]          # links to card/note
        assert c["extracted_by"] == "rule_based"
        assert c["extractor_version"] == ce.EXTRACTOR_VERSION
        assert len(c["evidence_excerpt"]) <= EVIDENCE_MAX_CHARS


def test_ambiguous_link_blocks(env) -> None:
    # Point a second source at the same card path -> ambiguous reverse lookup.
    env["source_repo"].record_generated_note(env["sid_b"], env["card_a"], "generated",
                                             "2026-07-05T00:00:00Z")
    with pytest.raises(ce.ClaimExtractionBlocked):
        ce.extract_claims_for_card(env["claim_repo"], env["source_repo"], env["config"],
                                   env["sid_a"], env["card_a"])
    assert env["claim_repo"].count_claims() == 0


def test_deleted_source_blocks(env) -> None:
    with sqlite3.connect(env["db"]) as c:
        c.execute("UPDATE source_intelligence_sources SET deleted=1 WHERE source_id=?", (env["sid_a"],))
    with pytest.raises(ce.ClaimExtractionBlocked):
        ce.extract_claims_for_card(env["claim_repo"], env["source_repo"], env["config"],
                                   env["sid_a"], env["card_a"])
    assert env["claim_repo"].count_claims() == 0


def test_stale_source_blocks_then_labels(env) -> None:
    env["source_repo"].mark_generated_notes_stale(env["sid_a"])
    # default: stale source blocks
    with pytest.raises(ce.ClaimExtractionBlocked):
        ce.extract_claims_for_card(env["claim_repo"], env["source_repo"], env["config"],
                                   env["sid_a"], env["card_a"])
    # opt-in: allowed but labeled stale
    res = ce.extract_claims_for_card(env["claim_repo"], env["source_repo"], env["config"],
                                     env["sid_a"], env["card_a"], allow_stale_source=True)
    assert res["source_state"] == "stale"
    assert all(c["source_state"] == "stale" for c in env["claim_repo"].get_claims_for_source(env["sid_a"]))


def test_ingest_seam_is_internal_and_validated(env) -> None:
    from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate, ClaimValidationError
    # manual seam writes only claim-owned tables and still enforces provenance
    with pytest.raises(ClaimValidationError):
        ce.ingest_claim_candidates(env["claim_repo"], None, [ClaimCandidate("fact", "x", "e")])
    ok = ce.ingest_claim_candidates(env["claim_repo"], env["sid_b"],
                                    [ClaimCandidate("fact", "x", "evidence")], extractor="manual")
    assert ok["ingested"] == 1
