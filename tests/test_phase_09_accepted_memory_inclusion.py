"""Phase 09 Addendum Prompt 03 — accepted-memory pipeline inclusion.

Proves an accepted long-term memory item flows through the deterministic reader, reviewed-memory
loader, approved-source manifest, vector dry-run plan, applied vector index, no-raw vector proof, and
coverage-parity closeout — while pending/rejected/superseded memory is excluded and nothing raw or
vector-shaped lands in SQLite.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.memory.models import MemoryItem
from hb_assistant.construction.second_brain.memory.store import write_memory_item
from hb_assistant.construction.second_brain.retrieval.accepted_memory_inclusion import (
    _accepted_item,
    _non_accepted_item,
    _seed_obsidian_apply_db,
    build_accepted_memory_loader_proof,
    build_accepted_memory_vector_coverage_proof,
)
from hb_assistant.construction.second_brain.retrieval.coverage_parity import (
    build_coverage_parity_closeout,
)
from hb_assistant.construction.second_brain.retrieval.memory_loader import (
    load_reviewed_memory_nodes,
)
from hb_assistant.construction.second_brain.retrieval.no_raw_vector_index_proof import (
    build_no_raw_vector_index_proof,
)
from hb_assistant.construction.second_brain.retrieval.readers import read_accepted_memory
from hb_assistant.construction.second_brain.retrieval.source_manifest import (
    build_approved_source_manifest,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    _mock_vector_writer,
    build_vector_index_apply,
    build_vector_index_dry_run,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _seed_memory_db(db: str) -> None:
    SQLiteMigrator(db_path=db).apply()
    write_memory_item(_accepted_item("acc-1"), db_path=db)
    for mid, status in (("p-1", "pending_review"), ("r-1", "rejected"), ("s-1", "superseded")):
        write_memory_item(_non_accepted_item(mid, status), db_path=db)


def test_accepted_memory_in_loader_output(tmp_path: Path) -> None:
    db = str(tmp_path / "m.sqlite")
    _seed_memory_db(db)
    nodes = load_reviewed_memory_nodes(db)
    assert len(nodes) == 1
    assert nodes[0]["source_family"] == "accepted_long_term_memory"
    assert nodes[0]["source_ref"] == "acc-1"


def test_accepted_memory_in_reader_and_manifest(tmp_path: Path) -> None:
    db = str(tmp_path / "m.sqlite")
    _seed_memory_db(db)
    reader = read_accepted_memory(None, db, None)
    assert len(reader) == 1 and reader[0].source_family == "accepted_long_term_memory"
    manifest = build_approved_source_manifest(db)
    assert int(manifest["families"]["reviewed_memory"]["approved_count"]) == 1


def test_non_accepted_excluded(tmp_path: Path) -> None:
    db = str(tmp_path / "m.sqlite")
    _seed_memory_db(db)
    # reader, loader, and manifest each see exactly the one accepted item
    assert len(read_accepted_memory(None, db, None)) == 1
    assert len(load_reviewed_memory_nodes(db)) == 1
    manifest = build_approved_source_manifest(db)
    assert int(manifest["families"]["reviewed_memory"]["approved_count"]) == 1


def test_accepted_memory_in_vector_dry_run(tmp_path: Path) -> None:
    db = str(tmp_path / "m.sqlite")
    _seed_memory_db(db)
    plan = build_vector_index_dry_run(db)
    assert "accepted_long_term_memory" in plan["per_family_node_count"]
    assert plan["vectors_persisted_to_sqlite"] is False
    assert plan["no_raw_attested"] is True


def test_vector_apply_includes_accepted_memory(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "m.sqlite")
        _seed_memory_db(db)
        applied = build_vector_index_apply(
            db, writer=_mock_vector_writer, persist_root=str(Path(tmp) / "vs")
        )
        assert applied["status"] == "applied"
        assert "accepted_long_term_memory" in applied["per_family_item_count"]
        assert applied["vectors_persisted_to_sqlite"] is False
        # no-raw vector proof passes after memory is indexed
        assert build_no_raw_vector_index_proof(db)["proof_passed"] is True


def test_coverage_closeout_reports_memory_covered(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "m.sqlite")
        _seed_memory_db(db)
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=str(Path(tmp) / "vs"))
        closeout = build_coverage_parity_closeout(db, write_evidence=False)
        planes = closeout["planes"]
        assert planes["memory_substrate_status"] == "covered"
        assert "accepted_long_term_memory" in planes["vector_indexed_families"]
        assert closeout["coverage_parity"]["coverage_parity_ok"] is True


def test_loader_proof_passes_and_writes_clean(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw

    ed = tmp_path / "ev"
    proof = build_accepted_memory_loader_proof(evidence_dir=str(ed), write_evidence=True)
    assert proof["proof_passed"] is True
    for name in ("accepted-memory-loader-proof.json", "accepted-memory-loader-proof.md"):
        _assert_no_raw((ed / name).read_text(encoding="utf-8"), name)


def test_vector_coverage_proof_passes_and_writes_clean(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw

    ed = tmp_path / "ev"
    proof = build_accepted_memory_vector_coverage_proof(evidence_dir=str(ed), write_evidence=True)
    assert proof["proof_passed"] is True
    assert proof["vector_family_delta_plus_one"] is True
    assert proof["memory_substrate_status_after"] == "covered"
    for name in (
        "accepted-memory-vector-coverage-proof.json",
        "accepted-memory-vector-coverage-proof.md",
    ):
        _assert_no_raw((ed / name).read_text(encoding="utf-8"), name)


def test_obsidian_baseline_excludes_memory(tmp_path: Path) -> None:
    # baseline obsidian fixture has no accepted memory until one is written
    with tempfile.TemporaryDirectory() as tmp:
        db = _seed_obsidian_apply_db(tmp)
        assert load_reviewed_memory_nodes(db) == []
        write_memory_item(
            MemoryItem(
                memory_id="late-1",
                memory_type="fact",
                statement_redacted="added later",
                confidence_class="high",
                review_status="accepted",
                source_refs=[{"source_family": "cross_source_relationships", "source_ref": "r"}],
            ),
            db_path=db,
        )
        assert len(load_reviewed_memory_nodes(db)) == 1


def test_cli_accepted_memory_loader_proof() -> None:
    result = CliRunner().invoke(
        app,
        ["second-brain", "retrieval", "accepted-memory-loader-proof", "--no-evidence", "--json"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_passed"] is True


def test_cli_accepted_memory_vector_coverage_proof() -> None:
    result = CliRunner().invoke(
        app,
        [
            "second-brain",
            "retrieval",
            "accepted-memory-vector-coverage-proof",
            "--no-evidence",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_passed"] is True
