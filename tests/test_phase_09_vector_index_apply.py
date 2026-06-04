"""Phase 09 Prompt 19 — vector index build apply (embed + receipts, fail-closed).

Proves the five required paths: (1) normal — an approved index applies via an offline `MockEmbedding`
LlamaIndex pipeline, writing vectors **outside SQLite** and persisting metadata-only `vector_index_runs`
+ `vector_index_items` receipts; (2) missing-policy — fail-closed, nothing persisted; (3) stale-schema —
fail-closed on a pre-V38 store; (4) unsafe-source — nodes failing the build rule are dropped (all-unsafe
→ `apply_blocked: no_indexable_nodes`); (5) no-raw / no-writeback — persisted rows carry no vector / text
/ raw columns and all guard columns stay 0, and the SDK-absent gate blocks fail-closed. The proof
artifacts and CLI exit codes are covered too. The real HuggingFace embed is a separate `integration`
smoke (excluded from the default-safe subset).
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
from hb_assistant.construction.second_brain.retrieval import vector_index
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    VectorIndexBuildError,
    _mock_vector_writer,
    _proof_db,
    build_vector_index_apply,
    build_vector_index_apply_proof,
    load_vector_index_apply_contract,
)

runner = CliRunner()

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_RUNS = "second_brain_retrieval_vector_index_runs"
_ITEMS = "second_brain_retrieval_vector_index_items"


def _counts(db: str) -> tuple[int, int]:
    conn = sqlite3.connect(db)
    try:
        runs = conn.execute(f"SELECT COUNT(*) FROM {_RUNS}").fetchone()[0]
        items = conn.execute(f"SELECT COUNT(*) FROM {_ITEMS}").fetchone()[0]
    finally:
        conn.close()
    return runs, items


def test_normal_path_apply_writes_vectors_outside_sqlite() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        persist_root = str(Path(td) / "vs")
        receipt = build_vector_index_apply(
            db, writer=_mock_vector_writer, persist_root=persist_root
        )
        assert receipt["status"] == "applied"
        assert receipt["total_items"] >= 1
        assert receipt["embedding_dim"] == 384
        assert receipt["vectors_persisted_to_sqlite"] is False
        assert receipt["vector_store_location"] == "external_filesystem"

        # Vectors are on the local filesystem, never in SQLite.
        persist_dir = Path(persist_root) / receipt["run_id"]
        assert persist_dir.exists() and any(persist_dir.iterdir())

        runs, items = _counts(db)
        assert runs == 1
        assert items == receipt["total_items"]
        # Receipt carries no raw shapes.
        assert not _SECRET_OR_URL.search(json.dumps(receipt, default=str))


def test_missing_policy_fail_closed_persists_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise VectorIndexBuildError("apply contract unavailable")

    monkeypatch.setattr(vector_index, "load_vector_index_apply_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(VectorIndexBuildError):
            build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=td)
        assert _counts(db) == (0, 0)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(VectorIndexBuildError):
            build_vector_index_apply(str(db), writer=_mock_vector_writer, persist_root=td)


def test_unsafe_source_blocks_no_indexable_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    unsafe_node = {
        "node_id": "n-unsafe",
        "source_family": "raw_prompt",  # non-embeddable family
        "source_ref": "x-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "review_status": "accepted",
        "review_required": False,
        "freshness_label": "current",
        "text_redacted": "[redacted]",
    }
    manifest_stub = {"manifest_id": "asm_stub", "manifest_hash": "0" * 64}

    def _gather(db_path: str | None, project_key: str | None) -> tuple[list[dict], dict]:
        return [unsafe_node], manifest_stub

    monkeypatch.setattr(vector_index, "_gather_approved_nodes", _gather)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        receipt = build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=td)
        assert receipt["status"] == "apply_blocked"
        assert receipt["blocker_reason"] == "no_indexable_nodes"
        assert _counts(db) == (0, 0)


def test_no_raw_no_writeback_and_sdk_absent_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = load_vector_index_apply_contract()
    forbidden = set(contract["forbidden_persisted_fields"])
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        receipt = build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=td)
        assert receipt["status"] == "applied"

        conn = sqlite3.connect(db)
        try:
            run_cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({_RUNS})")}
            item_cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({_ITEMS})")}
            guard_cols = [
                c
                for c in run_cols
                if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
            ]
            run_guard_sum = conn.execute(
                f"SELECT {'+'.join(guard_cols)} FROM {_RUNS}"
            ).fetchone()[0]
            item_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_ITEMS}"
            ).fetchone()[0]
        finally:
            conn.close()

        # No vector / text / raw columns persisted; every guard column stays 0.
        assert not (forbidden & (run_cols | item_cols))
        assert run_guard_sum == 0
        assert item_guard_sum == 0

    # SDK-absent gate: default writer + no SDK -> fail-closed, persists nothing.
    monkeypatch.setattr(vector_index, "_llama_index_available", lambda: False)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        receipt = build_vector_index_apply(db, persist_root=td)
        assert receipt["status"] == "apply_blocked"
        assert receipt["blocker_reason"] == "sdk_not_available"
        assert _counts(db) == (0, 0)


def test_apply_proof_passes_and_is_clean() -> None:
    proof = build_vector_index_apply_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["applied_item_count"] >= 1
    assert proof["embedding_dim"] == 384
    assert proof["vectors_written_outside_sqlite"] is True
    assert proof["vectors_persisted_to_sqlite"] is False
    assert proof["run_record_guard_clean"] is True
    assert proof["item_records_guard_clean"] is True
    assert proof["no_forbidden_persisted_columns"] is True
    assert proof["blocked_no_indexable_nodes"] is True
    assert all(c["passed"] for c in proof["cases"])
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_apply_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_vector_index_apply_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "vector-index-apply-proof.json"
    pm = tmp_path / "vector-index-apply-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


def test_cli_build_apply_proof_passes() -> None:
    res = runner.invoke(
        app, ["retrieval", "llamaindex", "build-apply-proof", "--no-evidence", "--json"]
    )
    assert res.exit_code == 0
    assert '"proof_passed": true' in res.stdout
    assert "guardrails" in res.stdout


@pytest.mark.integration
def test_apply_real_huggingface_embed_smoke() -> None:
    """Real local embed via the configured HuggingFace model (downloads weights; opt-in only)."""
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        receipt = build_vector_index_apply(db, persist_root=str(Path(td) / "vs"))
        assert receipt["status"] == "applied"
        assert receipt["embedding_dim"] == 384
        assert receipt["vectors_persisted_to_sqlite"] is False
        persist_dir = Path(td) / "vs" / receipt["run_id"]
        assert persist_dir.exists() and any(persist_dir.iterdir())
