"""Phase 09 Prompt 16 — approved Obsidian output loader (read-only, fail-closed).

Proves (1) the loader loads guard-clean nodes from an apply-mode index and the report is metadata-only;
(2) fail-closed when the embedding contract/seed is missing; (3) fail-closed on a stale (pre-V38) store;
(4) a dry-run-only index loads 0 nodes (unapproved never indexed) and the embedding guardrail rejects
tier-3 / non-embeddable / raw-shape candidates; (5) the loader + proof never mutate the store and carry
no raw text / shapes; plus (6) the proof writes guard-clean JSON+MD. CLI exit codes are covered too.
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
from hb_assistant.construction.second_brain.retrieval import embedding_policy, obsidian_loader
from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
    EmbeddingVectorPolicyError,
)
from hb_assistant.construction.second_brain.retrieval.obsidian_loader import (
    ObsidianLoaderError,
    build_obsidian_loader_proof,
    build_obsidian_loader_report,
    load_approved_obsidian_nodes,
)

runner = CliRunner()

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)


def _obsidian_db(tmp: str, mode: str) -> str:
    from hb_assistant.construction.second_brain.obsidian_index.indexer import build_index
    from hb_assistant.construction.second_brain.obsidian_linkage_proof import (
        write_linkage_fixture_vault,
    )

    vault = Path(tmp) / f"vault_{mode}"
    write_linkage_fixture_vault(vault)
    db = str(Path(tmp) / f"idx_{mode}.sqlite")
    build_index(mode=mode, vault_root=vault, db_path=db)
    return db


def test_normal_path_loads_apply_nodes() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _obsidian_db(td, "apply")
        nodes = load_approved_obsidian_nodes(db)
        assert len(nodes) >= 1
        assert all(n["source_family"] == "approved_obsidian_generated_outputs" for n in nodes)
        report = build_obsidian_loader_report(db)
        assert report["status"] == "loaded"
        assert report["loaded_count"] == len(nodes)
        # report is metadata-only — no text fields leaked
        for summary in report["nodes"]:
            assert "text_redacted" not in summary and "text" not in summary
        assert not _SECRET_OR_URL.search(json.dumps(report))


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise EmbeddingVectorPolicyError("contract unavailable")

    monkeypatch.setattr(obsidian_loader, "load_embedding_vector_policy_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _obsidian_db(td, "apply")
        with pytest.raises(EmbeddingVectorPolicyError):
            load_approved_obsidian_nodes(db)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(ObsidianLoaderError):
            load_approved_obsidian_nodes(str(db))


def test_dry_run_only_loads_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _obsidian_db(td, "dry_run")
        assert load_approved_obsidian_nodes(db) == []
        report = build_obsidian_loader_report(db)
        assert report["status"] == "empty"
        assert "no_approved_obsidian_notes" in report["warnings"]


def test_guardrail_excludes_unsafe_candidates() -> None:
    contract = embedding_policy.load_embedding_vector_policy_contract()
    seed = embedding_policy.load_embedding_vector_policy_seed()
    safe = {
        "source_family": "approved_obsidian_generated_outputs",
        "source_ref": "note-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "freshness_label": "current",
        "review_required": False,
        "review_status": "auto_advisory",
        "text_redacted": "Project Alpha Summary",
    }
    assert embedding_policy.validate_embedding_candidate(safe, contract=contract, seed=seed) == []
    unsafe = [
        {**safe, "review_tier": 3, "review_required": True, "review_status": "review_required"},
        {**safe, "source_family": "raw_email_body"},
        {k: v for k, v in safe.items() if k != "content_hash"},
        {**safe, "text_redacted": "Bea" + "rer " + "z" * 32},
    ]
    for cand in unsafe:
        assert embedding_policy.validate_embedding_candidate(cand, contract=contract, seed=seed), (
            cand
        )


def test_proof_passes_and_is_clean() -> None:
    proof = build_obsidian_loader_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["apply_loaded_count"] >= 1
    assert proof["dry_run_loaded_count"] == 0
    assert all(c["passed"] for c in proof["cases"])
    assert not _SECRET_OR_URL.search(json.dumps(proof))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_obsidian_loader_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "approved-obsidian-loader-proof.json"
    pm = tmp_path / "approved-obsidian-loader-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


def test_loader_does_not_mutate_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _obsidian_db(td, "apply")
        conn = sqlite3.connect(db)
        entries = conn.execute("SELECT COUNT(*) FROM obsidian_index_entries").fetchone()[0]
        manifests = conn.execute("SELECT COUNT(*) FROM obsidian_index_manifests").fetchone()[0]
        mig = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()

        # The loader opens the DB read-only (mode=ro) and must not change any row counts.
        load_approved_obsidian_nodes(db)
        build_obsidian_loader_report(db)

        conn = sqlite3.connect(db)
        assert conn.execute("SELECT COUNT(*) FROM obsidian_index_entries").fetchone()[0] == entries
        assert (
            conn.execute("SELECT COUNT(*) FROM obsidian_index_manifests").fetchone()[0] == manifests
        )
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == mig
        conn.close()


def test_cli_status_and_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    # status fail-closed -> exit 3
    def _boom(**kwargs: object) -> dict:
        raise ObsidianLoaderError("schema not ready")

    monkeypatch.setattr(obsidian_loader, "build_obsidian_loader_report", _boom)
    res = runner.invoke(app, ["retrieval", "obsidian-loader", "status", "--json"])
    assert res.exit_code == 3

    # proof pass -> exit 0
    monkeypatch.setattr(
        obsidian_loader,
        "build_obsidian_loader_proof",
        lambda *, write_evidence=True: {
            "command": "second-brain retrieval obsidian-loader proof",
            "proof_passed": True,
            "apply_loaded_count": 2,
            "dry_run_loaded_count": 0,
            "cases": [{"name": "safe_obsidian_node", "passed": True}],
        },
    )
    res = runner.invoke(app, ["retrieval", "obsidian-loader", "proof", "--no-evidence", "--json"])
    assert res.exit_code == 0
    assert "guardrails" in res.stdout
