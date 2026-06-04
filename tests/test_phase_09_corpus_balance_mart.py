"""Phase 09 Prompt 11 — retrieval corpus-balance + source-family coverage mart tests.

Exercises the read-only corpus-balance mart + fail-closed gate + proof over controlled populations: a
balanced corpus (3 covered families, no dominance → gate balanced), a missing-policy fail-closed path,
a stale-schema DB, a no-raw injection (fail-closed; value never echoed; DB unchanged), and an
imbalanced corpus (too few covered families → gate imbalanced, but the proof still validly measures
it). No live model call, no vault write outside tmp, no external writeback.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.corpus_balance_mart import (
    SEED_ENV_VAR,
    build_corpus_balance_mart,
    build_corpus_balance_proof,
)
from hb_assistant.construction.second_brain.obsidian_index import build_index
from hb_assistant.construction.second_brain.obsidian_linkage_proof import (
    write_linkage_fixture_vault,
)
from hb_assistant.construction.store import ConstructionStore

_REF = json.dumps({"project_key": "P1"})


def _seed_relationships(store: ConstructionStore, n: int) -> None:
    for i in range(n):
        store.upsert_cross_source_relationship(
            relationship_id=f"rel-{i}",
            source_family="document",
            source_record_type="document",
            source_record_ref=f"doc-{i}",
            target_family="procore",
            target_record_type="rfi",
            target_record_ref=f"rfi-{i}-hash",
            relationship_type="document_record_reference",
            confidence_class="deterministic",
            source_reference_json=_REF,
            project_key="P1",
        )


def _seed_evidence(store: ConstructionStore, n: int) -> None:
    for i in range(n):
        store.upsert_source_evidence_trail(
            evidence_trail_id=f"et-{i}",
            evidence_kind="document_relationship",
            source_refs_json=json.dumps([f"r{i}"]),
            confidence_class="deterministic",
            project_key="P1",
        )


def _seed_balanced_corpus(db: str, tmp_path: Path) -> None:
    """3 covered families (evidence trails / relationships / obsidian), balanced counts."""
    store = ConstructionStore(db)
    _seed_evidence(store, 2)
    _seed_relationships(store, 2)
    vault = tmp_path / "vault"
    write_linkage_fixture_vault(vault)  # 2 approved obsidian notes
    build_index(mode="apply", vault_root=vault, db_path=db)


def _write_policy(path: Path, *, min_covered: int, max_share: float) -> Path:
    path.write_text(
        f"version: test_corpus_policy\n"
        f"min_covered_families: {min_covered}\n"
        f"max_dominant_family_share: {max_share}\n"
        "deferred_families:\n"
        "  - meeting_prep_brief_sections\n"
        "  - review_controlled_correspondence_context\n",
        encoding="utf-8",
    )
    return path


def test_balanced_corpus_passes_gate(tmp_path: Path, monkeypatch) -> None:
    db = str(tmp_path / "corpus.sqlite3")
    _seed_balanced_corpus(db, tmp_path)
    policy = _write_policy(tmp_path / "policy.yaml", min_covered=3, max_share=0.6)
    monkeypatch.setenv(SEED_ENV_VAR, str(policy))

    proof = build_corpus_balance_proof(db)
    mart = proof["mart"]
    assert proof["proof_passed"] is True
    assert proof["policy_loaded"] is True
    assert proof["guard_violation"] is False
    assert proof["raw_content_findings"] == []
    assert proof["corpus_balance_ok"] is True
    assert proof["gate"]["verdict"] == "balanced"
    assert mart["covered_family_count"] >= 3
    assert mart["dominant_share"] <= 0.6


def test_missing_policy_fails_closed(tmp_path: Path, monkeypatch) -> None:
    db = str(tmp_path / "corpus.sqlite3")
    ConstructionStore(db)  # migrate, empty corpus
    monkeypatch.setenv(SEED_ENV_VAR, str(tmp_path / "nope" / "policy.yaml"))

    proof = build_corpus_balance_proof(db)
    assert proof["policy_loaded"] is False
    assert proof["policy_error"] == "CorpusBalancePolicyError"
    assert proof["proof_passed"] is False
    assert proof["corpus_balance_ok"] is False
    assert proof["gate"]["verdict"] == "policy_missing"


def test_stale_schema_is_handled_gracefully(tmp_path: Path) -> None:
    db = str(tmp_path / "stale.sqlite3")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    proof = build_corpus_balance_proof(db)
    assert proof["schema_version"] == 5
    assert proof["schema_ok"] is False
    assert proof["proof_passed"] is False
    assert proof["mart"]["total_corpus_rows"] == 0


def test_raw_content_injection_fails_closed(tmp_path: Path) -> None:
    db = str(tmp_path / "tainted.sqlite3")
    _seed_balanced_corpus(db, tmp_path)  # uses the committed default policy (no env override)
    before = build_corpus_balance_mart(db)["covered_family_count"]
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE cross_source_relationships SET signals_json = ? WHERE relationship_id = 'rel-0'",
        ("https://example.com/file?sig=abcdef0123456789abcdef",),
    )
    conn.commit()
    conn.close()

    proof = build_corpus_balance_proof(db)
    assert proof["proof_passed"] is False
    assert "cross_source_relationships.signals_json" in proof["raw_content_findings"]
    # The offending value is never echoed back — only the table.column location.
    assert "sig=abcdef" not in json.dumps(proof)
    # The read-only proof never mutates the DB (no-writeback): covered family count unchanged.
    after = build_corpus_balance_mart(db)["covered_family_count"]
    assert after == before


def test_imbalanced_corpus_is_measured_not_failed(tmp_path: Path) -> None:
    db = str(tmp_path / "imbalanced.sqlite3")
    store = ConstructionStore(db)
    _seed_relationships(store, 10)  # heavy relationships
    _seed_evidence(store, 1)  # tiny evidence → only 2 covered families
    # No env override → the committed default policy (min_covered_families = 5).
    proof = build_corpus_balance_proof(db)
    mart = proof["mart"]
    gate = proof["gate"]

    # The proof is VALID (policy + schema + guard-clean + no-raw) even though the corpus is imbalanced.
    assert proof["proof_passed"] is True
    assert proof["corpus_balance_ok"] is False
    assert gate["verdict"] == "imbalanced"
    assert mart["covered_family_count"] == 2
    assert any(reason.startswith("too_few_covered_families") for reason in gate["blocking_reasons"])
    assert any(w.startswith("empty_family:") for w in mart["warnings"])
