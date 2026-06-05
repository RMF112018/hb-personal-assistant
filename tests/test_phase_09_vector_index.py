"""Phase 09 Prompt 18 — vector index build dry run (read-only, fail-closed).

Proves (1) the dry-run build produces a metadata-only plan over the approved manifest's loader nodes and
a guard-clean `status='dry_run'` run record persists (no vectors in SQLite); (2) fail-closed when the
embedding/llamaindex policy is missing; (3) fail-closed on a stale (pre-V38) store; (4) the build rule
rejects nodes lacking review tier / confidence / source ref / freshness / no-raw proof; (5) the dry-run
build never mutates the store and carries no raw text/shapes; (6) `--apply` is deferred (fail-closed);
plus (7) the proof writes guard-clean JSON+MD. CLI exit codes are covered too.
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
from hb_assistant.construction.second_brain.retrieval import vector_index
from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
    EmbeddingVectorPolicyError,
    load_embedding_vector_policy_contract,
    load_embedding_vector_policy_seed,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    VectorIndexBuildError,
    _apply_build_rule,
    build_vector_index_dry_run,
    build_vector_index_dry_run_proof,
    persist_dry_run_record,
)

runner = CliRunner()

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)


def _proof_db(tmp: str) -> str:
    from hb_assistant.construction.second_brain.obsidian_index.indexer import build_index
    from hb_assistant.construction.second_brain.obsidian_linkage_proof import (
        write_linkage_fixture_vault,
    )

    vault = Path(tmp) / "vault"
    write_linkage_fixture_vault(vault)
    db = str(Path(tmp) / "vidx.sqlite")
    build_index(mode="apply", vault_root=vault, db_path=db)
    write_memory_item(
        MemoryItem(
            memory_id="m1",
            memory_type="fact",
            statement_redacted="[redacted project summary]",
            confidence_class="high",
            review_status="accepted",
            source_refs=[{"source_family": "cross_source_relationships", "source_ref": "rel-1"}],
        ),
        db_path=db,
    )
    return db


def _add_generated_output_fixture(db: str) -> None:
    """Add one manifest-eligible accepted research packet + one apply daily brief (with source refs + handoff lines).
    This exercises the generated-outputs loader path and increases dry-run node count.
    Uses raw inserts + explicit guard columns =0; temp DB only.
    """
    from hb_assistant.store.migrator import SQLiteMigrator

    SQLiteMigrator(db_path=db).apply()  # ensure packet/brief tables exist
    conn = sqlite3.connect(db)
    try:
        now = "2026-06-05T00:00:00+00:00"
        # Accepted research packet (eligible for generated_outputs)
        conn.execute(
            """
            INSERT OR IGNORE INTO second_brain_research_packets
            (packet_id, mode, topic_hash, project_key, source_ref_count, review_required_count,
             stale_unknown_count, conflict_count, context_quality_class, confidence_class,
             review_tier, review_tier_reason_code, review_status, advisory_classification,
             summary_redacted, status, created_utc,
             raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted,
             raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted,
             signed_url_persisted, download_url_persisted, external_writeback_performed)
            VALUES (?, 'mock', ?, 'P9', 2, 0, 0, 0, 'high', 'high', 1, 'T1', 'accepted', 'advisory',
                    '[redacted generated packet summary for vector test]', 'synthesized', ?,
                    0,0,0,0,0,0,0,0,0)
            """,
            ("pkt-gen-vec-1", "t" + "0" * 15, now),
        )

        # Apply daily brief run (eligible)
        conn.execute(
            """
            INSERT OR IGNORE INTO daily_brief_runs
            (brief_run_id, brief_date, mode, status, project_count, source_ref_count,
             review_required_count, stale_unknown_count, review_tier, degradation_mode,
             output_path_redacted, output_path_hash, generated_utc,
             raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted,
             raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted,
             signed_url_persisted, download_url_persisted, external_writeback_performed)
            VALUES (?, '2026-06-05', 'apply', 'synthesized', 1, 1, 0, 0, 1, 'none',
                    '12_Daily_Brief/2026-06-05_daily_brief.md', ?, ?,
                    0,0,0,0,0,0,0,0,0)
            """,
            ("brf-gen-vec-1", "h" + "0" * 15, now),
        )

        # Source ref for the brief (makes source_ref_count >0 and manifest eligible)
        conn.execute(
            """
            INSERT OR IGNORE INTO daily_brief_source_refs
            (daily_brief_source_ref_id, brief_run_id, source_family, source_ref, evidence_trail_id,
             confidence_class, review_required, stale_unknown)
            VALUES (?, ?, 'cross_source_relationships', 'rel-gen-1', NULL, 'high', 0, 0)
            """,
            ("sref-gen-1", "brf-gen-vec-1"),
        )

        # Handoff lines (provide redacted text_redacted for the brief node)
        conn.execute(
            """
            INSERT OR IGNORE INTO daily_brief_handoff_lines
            (line_id, brief_run_id, section, line_index, title_redacted, review_tier,
             source_refs_json, generated_utc,
             raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted,
             raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted,
             signed_url_persisted, download_url_persisted, external_writeback_performed)
            VALUES (?, ?, 'priority_actions', 0, 'Review generated packet pkt-gen-vec-1', 1,
                    '[{"source_family":"cross_source_relationships","source_ref":"rel-gen-1"}]', ?,
                    0,0,0,0,0,0,0,0,0)
            """,
            ("hl-gen-1", "brf-gen-vec-1", now),
        )
        conn.commit()
    finally:
        conn.close()


def test_normal_path_dry_run_and_persist() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        plan0 = build_vector_index_dry_run(db)
        count0 = plan0["total_nodes"]
        # Add manifest-eligible generated outputs (accepted packet + apply brief + refs + handoffs)
        # This exercises the new generated-outputs loader and must increase the dry-run node count.
        _add_generated_output_fixture(db)
        plan = build_vector_index_dry_run(db)
        assert plan["status"] == "dry_run"
        assert plan["total_nodes"] > count0, (
            "generated outputs loader must contribute additional approved nodes"
        )
        assert plan["planned_chunk_count"] >= plan["total_nodes"]
        assert plan["vectors_persisted_to_sqlite"] is False
        assert plan["read_only"] is True
        assert not _SECRET_OR_URL.search(json.dumps(plan))
        run_id = persist_dry_run_record(db, plan, policy_version=str(plan["policy_version"]))
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT run_id, status, item_count, raw_vector_content_persisted, "
            "external_writeback_performed FROM second_brain_retrieval_vector_index_runs"
        ).fetchall()
        conn.close()
        assert row == [(run_id, "dry_run", plan["total_nodes"], 0, 0)]


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise EmbeddingVectorPolicyError("contract unavailable")

    monkeypatch.setattr(vector_index, "load_embedding_vector_policy_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(EmbeddingVectorPolicyError):
            build_vector_index_dry_run(db)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(VectorIndexBuildError):
            build_vector_index_dry_run(str(db))


def test_build_rule_rejects_unsafe_nodes() -> None:
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    safe = {
        "source_family": "accepted_long_term_memory",
        "source_ref": "m-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "review_status": "accepted",
        "review_required": False,
        "freshness_label": "current",
        "text_redacted": "[redacted project summary]",
    }
    assert _apply_build_rule(safe, contract=contract, seed=seed) == []
    unsafe = [
        {k: v for k, v in safe.items() if k != "review_tier"},
        {k: v for k, v in safe.items() if k != "confidence_class"},
        {k: v for k, v in safe.items() if k != "source_ref"},
        {k: v for k, v in safe.items() if k != "freshness_label"},
        {**safe, "text_redacted": "Bea" + "rer " + "z" * 32},
        {**safe, "source_family": "raw_prompt"},
    ]
    for node in unsafe:
        assert _apply_build_rule(node, contract=contract, seed=seed), node


def test_dry_run_does_not_mutate_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        conn = sqlite3.connect(db)
        runs = conn.execute(
            "SELECT COUNT(*) FROM second_brain_retrieval_vector_index_runs"
        ).fetchone()[0]
        mig = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()

        # The dry-run build is read-only (mode=ro) and must not add a run row.
        build_vector_index_dry_run(db)

        conn = sqlite3.connect(db)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM second_brain_retrieval_vector_index_runs"
            ).fetchone()[0]
            == runs
            == 0
        )
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == mig
        conn.close()


def test_proof_passes_and_is_clean() -> None:
    proof = build_vector_index_dry_run_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["proof_total_nodes"] >= 1
    assert proof["dry_run_record_persisted"] is True
    assert proof["dry_run_record_guard_clean"] is True
    assert proof["vectors_persisted_to_sqlite"] is False
    assert all(c["passed"] for c in proof["cases"])
    assert not _SECRET_OR_URL.search(json.dumps(proof))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_vector_index_dry_run_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "vector-index-dry-run-proof.json"
    pm = tmp_path / "vector-index-dry-run-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


def test_cli_build_apply_blocked_and_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    # --apply now enabled; fail-closed apply_blocked surfaces exit 3 (no indexable nodes)
    monkeypatch.setattr(
        vector_index,
        "build_vector_index_apply",
        lambda **kwargs: {
            "command": "second-brain retrieval llamaindex build --apply",
            "status": "apply_blocked",
            "blocker_reason": "no_indexable_nodes",
            "vectors_persisted_to_sqlite": False,
            "vector_store_location": "external_filesystem",
        },
    )
    res = runner.invoke(app, ["retrieval", "llamaindex", "build", "--apply", "--json"])
    assert res.exit_code == 3
    assert "apply_blocked" in res.stdout

    # build dry-run fail-closed -> exit 3
    def _boom(**kwargs: object) -> dict:
        raise VectorIndexBuildError("schema not ready")

    monkeypatch.setattr(vector_index, "build_vector_index_dry_run", _boom)
    res = runner.invoke(app, ["retrieval", "llamaindex", "build", "--json"])
    assert res.exit_code == 3

    # build-proof pass -> exit 0
    monkeypatch.setattr(
        vector_index,
        "build_vector_index_dry_run_proof",
        lambda *, write_evidence=True: {
            "command": "second-brain retrieval llamaindex build-proof",
            "proof_passed": True,
            "proof_total_nodes": 3,
            "dry_run_record_persisted": True,
            "cases": [{"name": "safe_node", "passed": True}],
        },
    )
    res = runner.invoke(app, ["retrieval", "llamaindex", "build-proof", "--no-evidence", "--json"])
    assert res.exit_code == 0
    assert "guardrails" in res.stdout
