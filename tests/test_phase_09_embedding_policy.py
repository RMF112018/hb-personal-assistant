"""Phase 09 Prompt 14 — embedding + vector-store policy + no-raw guardrails (read-only).

Proves (1) the policy contract/seed load and a safe candidate validates clean on a migrated-to-V38
store; (2) fail-closed when the contract or seed is missing/invalid; (3) `schema_ready=False` on a
stale (pre-V38) store; (4) the no-raw guardrail rejects every unsafe candidate (excluded/non-embeddable
family, raw body, signed URL, vector blob, secret shape, missing metadata, unresolved review) while
passing safe candidates — `proof_passed=True`; (5) the status + proof never mutate the store and the
committed policy is metadata-only; plus (6) the proof writes guard-clean JSON+MD artifacts. CLI exit
codes (0 ready / 3 not-ready / 3 contract-failure) are covered too.
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
from hb_assistant.construction.second_brain.retrieval import embedding_policy
from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
    EmbeddingVectorPolicyError,
    build_embedding_vector_policy_status,
    build_no_raw_vector_policy_proof,
    embeddable_families,
    load_embedding_vector_policy_contract,
    load_embedding_vector_policy_seed,
    validate_embedding_candidate,
)
from hb_assistant.construction.second_brain.retrieval.policy import EXCLUDED_FAMILIES
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)


def _migrated_db(td: str) -> str:
    db = Path(td) / "v38.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _safe_candidate() -> dict:
    return {
        "source_family": "phase_07d_source_evidence_trails",
        "source_ref": "evidence_trail:abc123",
        "content_hash": "f" * 64,
        "confidence_class": "deterministic",
        "review_tier": 2,
        "freshness_label": "current",
        "review_required": False,
    }


def test_normal_path() -> None:
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    assert validate_embedding_candidate(_safe_candidate(), contract=contract, seed=seed) == []
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        r = build_embedding_vector_policy_status(db_path=db)
        assert r["config_valid"] is True
        assert r["schema_ready"] is True
        assert r["read_only"] is True
        assert r["embeddable_family_count"] == 7


def test_embeddable_families_exclude_raw() -> None:
    seed = load_embedding_vector_policy_seed()
    fams = embeddable_families(seed)
    assert not (set(fams) & EXCLUDED_FAMILIES)
    assert "meeting_prep_brief_sections" not in fams  # deferred (no reader)


def test_missing_contract_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedding_policy, "load_phase_09_contract", lambda name: {})
    with pytest.raises(EmbeddingVectorPolicyError):
        build_embedding_vector_policy_status()


def test_missing_seed_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise EmbeddingVectorPolicyError("seed missing")

    monkeypatch.setattr(embedding_policy, "load_embedding_vector_policy_seed", _boom)
    with pytest.raises(EmbeddingVectorPolicyError):
        build_embedding_vector_policy_status()


def test_stale_schema_not_ready() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        r = build_embedding_vector_policy_status(db_path=str(db))
        assert r["schema_ready"] is False
        assert "schema_not_ready" in r["blockers"]


def test_unsafe_candidates_rejected() -> None:
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    base = _safe_candidate()
    unsafe = [
        {**base, "source_family": "raw_email_body"},
        {**base, "source_family": "meeting_prep_brief_sections"},
        {**base, "raw_body": "text"},
        {**base, "signed_url": "ref"},
        {**base, "embedding": [0.1, 0.2]},
        {**base, "content_hash": "Bea" + "rer " + "z" * 32},
        {k: v for k, v in base.items() if k != "source_ref"},
        {**base, "review_required": True, "review_status": "review_required"},
    ]
    for cand in unsafe:
        assert validate_embedding_candidate(cand, contract=contract, seed=seed), cand


def test_no_raw_proof_passes_and_is_clean() -> None:
    proof = build_no_raw_vector_policy_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["case_count"] == 9
    # safe passes; every planted-unsafe is rejected
    by_name = {c["name"]: c for c in proof["cases"]}
    assert by_name["safe_candidate"]["rejected"] is False
    assert all(c["rejected"] for c in proof["cases"] if c["name"] != "safe_candidate")
    # the proof never echoes a raw/secret/url shape
    assert not _SECRET_OR_URL.search(json.dumps(proof))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_no_raw_vector_policy_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "embedding-vector-policy-no-raw-proof.json"
    pm = tmp_path / "embedding-vector-policy-no-raw-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


def test_committed_policy_is_metadata_only() -> None:
    seed = load_embedding_vector_policy_seed()
    for key, value in seed.items():
        s = str(value)
        assert not _SECRET_OR_URL.search(s), f"{key} has a URL/secret shape"
        if not isinstance(value, list):
            assert not s.startswith("/"), f"{key} looks like an absolute path"


def test_status_does_not_mutate_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        before = Path(db).stat().st_size
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT COUNT(*) FROM second_brain_retrieval_vector_index_items"
        ).fetchone()[0]
        mig = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()

        build_embedding_vector_policy_status(db_path=db)
        build_no_raw_vector_policy_proof(write_evidence=False)

        conn = sqlite3.connect(db)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM second_brain_retrieval_vector_index_items"
            ).fetchone()[0]
            == rows
            == 0
        )
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == mig
        conn.close()
        assert Path(db).stat().st_size == before


def test_cli_status_and_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    # not-ready status -> exit 3
    monkeypatch.setattr(
        embedding_policy,
        "build_embedding_vector_policy_status",
        lambda: {
            "command": "second-brain retrieval embedding-policy status",
            "policy_loaded": True,
            "config_valid": True,
            "schema_ready": False,
            "embedding_provider": "local",
            "embedding_dim": 384,
            "vector_store_kind": "simple",
            "embeddable_family_count": 7,
            "blockers": ["schema_not_ready"],
        },
    )
    res = runner.invoke(app, ["retrieval", "embedding-policy", "status", "--json"])
    assert res.exit_code == 3

    # contract failure -> exit 3
    def _boom() -> dict:
        raise EmbeddingVectorPolicyError("contract unavailable")

    monkeypatch.setattr(embedding_policy, "build_embedding_vector_policy_status", _boom)
    res = runner.invoke(app, ["retrieval", "embedding-policy", "status", "--json"])
    assert res.exit_code == 3

    # proof pass -> exit 0
    monkeypatch.setattr(
        embedding_policy,
        "build_no_raw_vector_policy_proof",
        lambda *, write_evidence=True: {
            "command": "second-brain retrieval embedding-policy no-raw-proof",
            "proof_passed": True,
            "cases": [{"name": "safe_candidate", "passed": True}],
        },
    )
    res = runner.invoke(
        app, ["retrieval", "embedding-policy", "no-raw-proof", "--no-evidence", "--json"]
    )
    assert res.exit_code == 0
    assert "guardrails" in res.stdout
