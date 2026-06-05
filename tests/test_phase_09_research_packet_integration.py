"""Phase 09 Prompt 22 — research packet integration (semantic context routed via packet only).

Proves the five required paths: (1) normal — semantic context routes into a research packet (advisory),
never an answer; (2) missing-policy — fail-closed; (3) stale-schema — fail-closed on a pre-V38 store;
(4) unsafe-source — an excluded source family fails closed (never queried); (5) no-raw / no-writeback —
the route summary carries no raw query/excerpt and persists nothing by default; the persisted packet
receipt is metadata-only + guard-clean; synthesis has no direct semantic path (no bypass);
`assembles_final_answer=false`. Plus the proof. The real-HF semantic-packet smoke is an `integration` test.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.research import semantic_packet as sp
from hb_assistant.construction.second_brain.research.semantic_packet import (
    SemanticPacketError,
    build_semantic_research_packet,
    build_semantic_research_packet_proof,
)
from hb_assistant.construction.second_brain.retrieval.hybrid_broker import (
    HybridRetrievalError,
    _mock_embed_model,
)
from hb_assistant.construction.second_brain.retrieval.metadata_filter import (
    MetadataFilter,
    MetadataFilterError,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    _mock_vector_writer,
    _proof_db,
    build_vector_index_apply,
)

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_PACKETS = "second_brain_research_packets"


def _applied_db(td: str) -> tuple[str, str]:
    db = _proof_db(td)
    persist_root = str(Path(td) / "vs")
    build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
    return db, persist_root


def _packet_rows(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {_PACKETS}").fetchone()[0]
    finally:
        conn.close()


def test_normal_semantic_routes_into_packet() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_semantic_research_packet(
            "project summary status",
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
        )
        assert result["status"] == "ok"
        assert result["route"] == "research_packet_only"
        assert result["synthesis_performed"] is False
        assert result["assembles_final_answer"] is False
        assert result["semantic_count"] >= 1
        assert result["packet"]["advisory_classification"] == "advisory"
        # the route returns a packet, never an answer
        assert "answer" not in result and "answer_redacted" not in result
        assert result["read_only"] is True
        # default build persists nothing
        assert _packet_rows(db) == 0


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise SemanticPacketError("integration contract unavailable")

    monkeypatch.setattr(sp, "load_research_packet_integration_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        with pytest.raises(SemanticPacketError):
            build_semantic_research_packet(
                "q", db_path=db, embed_model=_mock_embed_model(), persist_root=persist_root
            )


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(HybridRetrievalError):
            build_semantic_research_packet("q", db_path=str(db), mode="deterministic_only")


def test_unsafe_source_excluded_family_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        with pytest.raises(MetadataFilterError):
            build_semantic_research_packet(
                "q",
                db_path=db,
                mode="hybrid",
                embed_model=_mock_embed_model(),
                persist_root=persist_root,
                metadata_filter=MetadataFilter(source_families=("raw_email_body",)),
            )


def test_no_raw_no_writeback_and_no_bypass() -> None:
    raw_query = "what is the latest status of the active project summary"
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        # default build: persists nothing; no raw query emitted
        result = build_semantic_research_packet(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
        )
        blob = json.dumps(result, default=str)
        assert raw_query not in blob
        assert not _SECRET_OR_URL.search(blob)
        assert _packet_rows(db) == 0

        # emit_receipt: persisted packet receipt is metadata-only + guard-clean
        build_semantic_research_packet(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
            emit_receipt=True,
        )
        conn = sqlite3.connect(db)
        try:
            assert conn.execute(f"SELECT COUNT(*) FROM {_PACKETS}").fetchone()[0] >= 1
            cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({_PACKETS})")]
            guard_cols = [
                c
                for c in cols
                if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
            ]
            if guard_cols:
                gsum = conn.execute(
                    f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_PACKETS}"
                ).fetchone()[0]
                assert gsum == 0
        finally:
            conn.close()

    # no bypass: synthesis agent has no direct semantic/hybrid path
    assert sp._synthesis_has_no_semantic_path() is True


def test_proof_passes_and_is_clean() -> None:
    proof = build_semantic_research_packet_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["route_is_research_packet_only"] is True
    assert proof["semantic_context_in_packet"] is True
    assert proof["packet_advisory"] is True
    assert proof["returns_packet_not_answer"] is True
    assert proof["packet_receipt_persisted_metadata_only"] is True
    assert proof["synthesis_has_no_semantic_path"] is True
    assert proof["excluded_family_fail_closed"] is True
    assert proof["raw_query_not_emitted"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_semantic_research_packet_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "research-packet-integration-proof.json"
    pm = tmp_path / "research-packet-integration-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


@pytest.mark.integration
def test_semantic_packet_real_huggingface_smoke() -> None:
    """Real local semantic→packet route via the configured HuggingFace model (downloads weights)."""
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        persist_root = str(Path(td) / "vs")
        build_vector_index_apply(db, persist_root=persist_root)
        result = build_semantic_research_packet(
            "project summary", db_path=db, mode="hybrid", persist_root=persist_root
        )
        assert result["status"] == "ok"
        assert result["route"] == "research_packet_only"
        assert result["synthesis_performed"] is False
        assert result["semantic_count"] >= 1
