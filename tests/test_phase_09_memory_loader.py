"""Phase 09 Prompt 17 — reviewed memory loader (read-only, fail-closed).

Proves (1) the loader loads guard-clean nodes from accepted memory and the report is metadata-only;
(2) fail-closed when the embedding contract/seed is missing; (3) fail-closed on a stale (pre-V38) store;
(4) a pending/rejected-only store loads 0 nodes (unreviewed never loaded) and the embedding guardrail
rejects non-embeddable / raw-shape / missing-metadata / unresolved candidates; (5) the loader + proof
never mutate the store and carry no raw statement text / shapes; plus (6) the proof writes guard-clean
JSON+MD. CLI exit codes are covered too.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.memory.models import MemoryItem
from hb_assistant.construction.second_brain.memory.store import write_memory_item
from hb_assistant.construction.second_brain.retrieval import embedding_policy, memory_loader
from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
    EmbeddingVectorPolicyError,
)
from hb_assistant.construction.second_brain.retrieval.memory_loader import (
    MemoryLoaderError,
    build_reviewed_memory_loader_proof,
    build_reviewed_memory_loader_report,
    load_reviewed_memory_nodes,
)
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)


def _memory_db(tmp: str, status: str) -> str:
    db = str(Path(tmp) / f"mem_{status}.db")
    SQLiteMigrator(db_path=db).apply()
    write_memory_item(
        MemoryItem(
            memory_id="m1",
            memory_type="fact",
            statement_redacted="[redacted project summary]",
            confidence_class="high",
            review_status=status,
            source_refs=[{"source_family": "cross_source_relationships", "source_ref": "rel-1"}],
        ),
        db_path=db,
    )
    return db


def test_normal_path_loads_accepted_memory() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _memory_db(td, "accepted")
        nodes = load_reviewed_memory_nodes(db)
        assert len(nodes) == 1
        assert nodes[0]["source_family"] == "accepted_long_term_memory"
        report = build_reviewed_memory_loader_report(db)
        assert report["status"] == "loaded"
        assert report["loaded_count"] == 1
        for summary in report["nodes"]:
            assert "text_redacted" not in summary and "statement_redacted" not in summary
        assert not _SECRET_OR_URL.search(json.dumps(report))


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise EmbeddingVectorPolicyError("contract unavailable")

    monkeypatch.setattr(memory_loader, "load_embedding_vector_policy_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _memory_db(td, "accepted")
        with pytest.raises(EmbeddingVectorPolicyError):
            load_reviewed_memory_nodes(db)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(MemoryLoaderError):
            load_reviewed_memory_nodes(str(db))


def test_pending_only_loads_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _memory_db(td, "pending_review")
        assert load_reviewed_memory_nodes(db) == []
        report = build_reviewed_memory_loader_report(db)
        assert report["status"] == "empty"
        assert "no_reviewed_memory" in report["warnings"]


def test_guardrail_excludes_unsafe_candidates() -> None:
    contract = embedding_policy.load_embedding_vector_policy_contract()
    seed = embedding_policy.load_embedding_vector_policy_seed()
    safe = {
        "source_family": "accepted_long_term_memory",
        "source_ref": "m-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "freshness_label": "current",
        "review_required": False,
        "review_status": "accepted",
        "text_redacted": "[redacted project summary]",
    }
    assert embedding_policy.validate_embedding_candidate(safe, contract=contract, seed=seed) == []
    unsafe = [
        {**safe, "source_family": "raw_prompt"},
        {k: v for k, v in safe.items() if k != "content_hash"},
        {**safe, "text_redacted": "Bea" + "rer " + "z" * 32},
        {**safe, "review_required": True, "review_status": "pending_review"},
    ]
    for cand in unsafe:
        assert embedding_policy.validate_embedding_candidate(cand, contract=contract, seed=seed), (
            cand
        )


def test_proof_passes_and_is_clean() -> None:
    proof = build_reviewed_memory_loader_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["accepted_loaded_count"] >= 1
    assert proof["pending_loaded_count"] == 0
    assert all(c["passed"] for c in proof["cases"])
    assert not _SECRET_OR_URL.search(json.dumps(proof))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_reviewed_memory_loader_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "reviewed-memory-loader-proof.json"
    pm = tmp_path / "reviewed-memory-loader-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


def test_loader_does_not_mutate_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _memory_db(td, "accepted")
        conn = sqlite3.connect(db)
        items = conn.execute("SELECT COUNT(*) FROM long_term_memory_items").fetchone()[0]
        mig = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()

        # The loader opens the DB read-only (mode=ro) and must not change any row counts.
        load_reviewed_memory_nodes(db)
        build_reviewed_memory_loader_report(db)

        conn = sqlite3.connect(db)
        assert conn.execute("SELECT COUNT(*) FROM long_term_memory_items").fetchone()[0] == items
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == mig
        conn.close()


def test_cli_status_and_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    # status fail-closed -> exit 3
    def _boom(**kwargs: object) -> dict:
        raise MemoryLoaderError("schema not ready")

    monkeypatch.setattr(memory_loader, "build_reviewed_memory_loader_report", _boom)
    res = runner.invoke(app, ["retrieval", "memory-loader", "status", "--json"])
    assert res.exit_code == 3

    # proof pass -> exit 0
    monkeypatch.setattr(
        memory_loader,
        "build_reviewed_memory_loader_proof",
        lambda *, write_evidence=True: {
            "command": "second-brain retrieval memory-loader proof",
            "proof_passed": True,
            "accepted_loaded_count": 1,
            "pending_loaded_count": 0,
            "cases": [{"name": "safe_memory_node", "passed": True}],
        },
    )
    res = runner.invoke(app, ["retrieval", "memory-loader", "proof", "--no-evidence", "--json"])
    assert res.exit_code == 0
    assert "guardrails" in res.stdout
