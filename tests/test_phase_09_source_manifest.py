"""Phase 09 Prompt 15 — approved index source manifests (read-only, fail-closed).

Proves (1) the builder enumerates approved, source-linked records and persists a guard-clean summary
row; (2) fail-closed when the contract or seed is missing/invalid; (3) fail-closed on a stale (pre-V38)
store; (4) the approval/no-raw guardrail excludes every unsafe candidate (excluded family, excluded/
pending review status, unresolved high-impact, missing metadata, forbidden field, raw shape) while
approving safe ones — `proof_passed=True`, and an unresolved-high-impact / pending entry never enters
the approved set; (5) build + proof never mutate the store and the committed policy is metadata-only;
plus (6) the proof writes guard-clean JSON+MD. CLI exit codes are covered too.
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
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.second_brain.daily_brief import run_daily_brief
from hb_assistant.construction.second_brain.memory.models import MemoryItem
from hb_assistant.construction.second_brain.memory.store import write_memory_item
from hb_assistant.construction.second_brain.obsidian_index import build_index
from hb_assistant.construction.second_brain.reasoning import MockClaudeAdapter
from hb_assistant.construction.second_brain.retrieval import source_manifest
from hb_assistant.construction.second_brain.retrieval.source_manifest import (
    ApprovedSourceManifestError,
    build_approved_source_manifest,
    build_approved_source_manifest_proof,
    persist_approved_source_manifest,
    validate_manifest_entry,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)


def _migrated_db(td: str) -> str:
    db = Path(td) / "v38.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_normal_path_build_and_persist() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        write_memory_item(
            MemoryItem(
                memory_id="m1",
                memory_type="fact",
                statement_redacted="[redacted]",
                confidence_class="high",
                review_status="accepted",
            ),
            db_path=db,
        )
        manifest = build_approved_source_manifest(db_path=db)
        assert manifest["status"] == "approved"
        assert manifest["approved_ref_count"] == 1
        assert manifest["families"]["reviewed_memory"]["approved_count"] == 1
        assert manifest["read_only"] is True
        # manifest_hash is stable for the same approved set
        again = build_approved_source_manifest(db_path=db)
        assert again["manifest_hash"] == manifest["manifest_hash"]
        # persist a single guard-clean summary row
        mid = persist_approved_source_manifest(
            db, manifest, policy_version=manifest["policy_version"]
        )
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT manifest_id, approved_ref_count, status, raw_vector_content_persisted, "
            "external_writeback_performed FROM second_brain_retrieval_approved_source_manifests"
        ).fetchall()
        conn.close()
        assert row == [(mid, 1, "approved", 0, 0)]


def test_missing_contract_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source_manifest, "load_phase_09_contract", lambda name: {})
    with pytest.raises(ApprovedSourceManifestError):
        build_approved_source_manifest()


def test_missing_seed_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise ApprovedSourceManifestError("seed missing")

    monkeypatch.setattr(source_manifest, "load_approved_source_manifest_seed", _boom)
    with pytest.raises(ApprovedSourceManifestError):
        build_approved_source_manifest()


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(ApprovedSourceManifestError):
            build_approved_source_manifest(db_path=str(db))


def test_operator_manifest_is_empty_and_honest() -> None:
    # Against a freshly-migrated store with no approved sources the manifest is empty (not a failure).
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        manifest = build_approved_source_manifest(db_path=db)
        assert manifest["status"] == "empty"
        assert manifest["approved_ref_count"] == 0
        assert "no_approved_sources" in manifest["warnings"]


def test_daily_brief_output_populates_approved_obsidian_sources(tmp_path: Path) -> None:
    db = _migrated_db(str(tmp_path))
    store = ConstructionStore(db)
    store.upsert_cross_source_relationship(
        relationship_id="rel-1",
        source_family="email",
        source_record_type="message",
        source_record_ref="m1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi1",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=False,
    )

    result = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db,
        mode="apply",
        adapter=MockClaudeAdapter(),
        emit_receipt=True,
    )
    assert result.applied is True
    assert result.output_path_redacted == (
        "Construction Intelligence/Phase 08A Daily Briefs/2026-06-02_daily_brief.md"
    )

    vault_root = PathPolicy().get_vault_root()
    dry_run_index = build_index(mode="dry_run", vault_root=vault_root, db_path=db)
    assert dry_run_index.entry_count >= 1
    assert any(
        e.approved_root_label == "Construction Intelligence/Phase 08A Daily Briefs"
        for e in dry_run_index.entries
    )

    generated_manifest = build_approved_source_manifest(db_path=db)
    assert generated_manifest["approved_ref_count"] > 0
    assert generated_manifest["families"]["generated_outputs"]["approved_count"] > 0
    assert generated_manifest["families"]["approved_obsidian_outputs"]["approved_count"] == 0

    build_index(mode="apply", vault_root=vault_root, db_path=db)
    manifest = build_approved_source_manifest(db_path=db)
    assert manifest["approved_ref_count"] > 0
    assert manifest["families"]["generated_outputs"]["approved_count"] > 0
    assert manifest["families"]["approved_obsidian_outputs"]["approved_count"] > 0
    assert "generated_outputs" in manifest["families"]
    assert "approved_obsidian_outputs" in manifest["families"]
    # Prompt 37: content change (new what_matters + ranked) still populates same approved paths (root unchanged)


def test_unsafe_candidates_excluded() -> None:
    from hb_assistant.construction.second_brain.retrieval.source_manifest import (
        load_approved_source_manifest_contract,
    )

    contract = load_approved_source_manifest_contract()
    base = {
        "source_family": "generated_outputs",
        "source_ref": "generated_outputs:ref-1",
        "content_hash": "f" * 64,
        "review_tier": 1,
        "review_status": "accepted",
        "confidence_class": "deterministic",
        "review_required": False,
    }
    assert validate_manifest_entry(base, contract=contract) == []
    unsafe = [
        {**base, "source_family": "raw_email_body"},
        {**base, "review_status": "rejected"},
        {**base, "review_status": "pending_review"},
        {**base, "review_tier": 3, "review_required": True, "review_status": "review_required"},
        {k: v for k, v in base.items() if k != "content_hash"},
        {**base, "raw_body": "x"},
        {**base, "content_hash": "Bea" + "rer " + "z" * 32},
    ]
    for cand in unsafe:
        assert validate_manifest_entry(cand, contract=contract), cand


def test_proof_passes_and_is_clean() -> None:
    proof = build_approved_source_manifest_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    by_name = {c["name"]: c for c in proof["cases"]}
    assert by_name["safe_reviewed_memory"]["approved"] is True
    assert by_name["unresolved_high_impact"]["approved"] is False
    assert by_name["pending_review_status"]["approved"] is False
    assert all(c["approved"] is False for c in proof["cases"] if not c["name"].startswith("safe_"))
    assert not _SECRET_OR_URL.search(json.dumps(proof))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_approved_source_manifest_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "approved-source-manifest-proof.json"
    pm = tmp_path / "approved-source-manifest-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


def test_build_and_proof_do_not_mutate_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT COUNT(*) FROM second_brain_retrieval_approved_source_manifests"
        ).fetchone()[0]
        mig = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()

        build_approved_source_manifest(db_path=db)
        build_approved_source_manifest_proof(write_evidence=False)

        conn = sqlite3.connect(db)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM second_brain_retrieval_approved_source_manifests"
            ).fetchone()[0]
            == rows
            == 0
        )
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == mig
        conn.close()


def test_cli_build_and_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    # build fail-closed -> exit 3
    def _boom(**kwargs: object) -> dict:
        raise ApprovedSourceManifestError("schema not ready")

    monkeypatch.setattr(source_manifest, "build_approved_source_manifest", _boom)
    res = runner.invoke(app, ["retrieval", "approved-sources", "build", "--json"])
    assert res.exit_code == 3

    # proof pass -> exit 0
    monkeypatch.setattr(
        source_manifest,
        "build_approved_source_manifest_proof",
        lambda *, write_evidence=True: {
            "command": "second-brain retrieval approved-sources proof",
            "proof_passed": True,
            "cases": [{"name": "safe_reviewed_memory", "passed": True}],
        },
    )
    res = runner.invoke(app, ["retrieval", "approved-sources", "proof", "--no-evidence", "--json"])
    assert res.exit_code == 0
    assert "guardrails" in res.stdout
