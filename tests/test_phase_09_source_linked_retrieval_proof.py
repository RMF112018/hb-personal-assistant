"""Phase 09 Prompt 34 — source-linked retrieval proof tests.

Covers the normal path, missing-policy fail-closed, stale-schema fail-closed, unsafe-source linkage
accounting, the no-raw/no-writeback proof, and guard-clean artifact writing.
"""

from __future__ import annotations

import sqlite3

import pytest

from hb_assistant.construction.second_brain.retrieval import source_linked_proof as slp
from hb_assistant.store.migrator import SQLiteMigrator


def _migrated_db(tmp_path) -> str:
    db = str(tmp_path / "operator.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


class _StubResult:
    """Duck-typed retrieval result for exercising ``_link_status`` (RetrievalItem itself forbids raw
    families, so an excluded-family case can only be represented by a stub)."""

    def __init__(self, source_family: str, source_ref: str) -> None:
        self.source_family = source_family
        self.source_ref = source_ref


def test_normal_proof_every_result_source_linked():
    proof = slp.build_source_linked_retrieval_proof_proof(write_evidence=False)

    assert proof["proof_passed"] is True
    assert proof["every_result_source_linked"] is True
    assert proof["result_count"] > 0
    assert proof["unlinked_count"] == 0
    assert proof["linked_count"] == proof["result_count"]
    assert proof["makes_determination"] is False


def test_missing_policy_fail_closed(tmp_path, monkeypatch):
    def _boom() -> dict:
        raise slp.SourceLinkedRetrievalProofError("contract missing")

    monkeypatch.setattr(slp, "load_source_linked_retrieval_proof_contract", _boom)
    with pytest.raises(slp.SourceLinkedRetrievalProofError):
        slp.build_source_linked_retrieval_proof(_migrated_db(tmp_path))


def test_stale_schema_fail_closed(tmp_path):
    empty = str(tmp_path / "empty.sqlite")
    sqlite3.connect(empty).close()  # no schema_migrations
    with pytest.raises(slp.SourceLinkedRetrievalProofError):
        slp.build_source_linked_retrieval_proof(empty)


def test_unsafe_source_counts_unlinked():
    # one linked, one excluded-family (raw_prompt), one empty source_ref
    items = [
        _StubResult("cross_source_relationships", "rel-1"),
        _StubResult("raw_prompt", "x-1"),
        _StubResult("email", ""),
    ]
    ls = slp._link_status(items)
    assert ls["result_count"] == 3
    assert ls["linked_count"] == 1
    assert ls["unlinked_count"] == 2
    assert ls["status"] == "unlinked_found"
    # empty list is honest 'empty', not a pass
    assert slp._link_status([])["status"] == "empty"


def test_no_raw_no_writeback_proof_clean():
    proof = slp.build_source_linked_retrieval_proof_proof(write_evidence=False)

    assert proof["no_raw_emitted"] is True
    assert proof["rows_persisted_guard_clean"] is True
    assert proof["read_only_default_no_persist"] is True


def test_proof_writes_guard_clean_artifacts(tmp_path):
    out_dir = tmp_path / "evidence"
    proof = slp.build_source_linked_retrieval_proof_proof(
        evidence_dir=str(out_dir), write_evidence=True
    )

    json_path = out_dir / "source-linked-retrieval-proof.json"
    md_path = out_dir / "source-linked-retrieval-proof.md"
    assert json_path.exists() and md_path.exists()
    assert proof["proof_passed"] is True

    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    for token in ("BEGIN", "PRIVATE KEY", "signed_url", "download_url", "secret", "text_redacted"):
        assert token not in text
