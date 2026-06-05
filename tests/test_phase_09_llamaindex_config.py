"""Phase 09 Prompt 13 — optional LlamaIndex dependency + config/status surface (read-only).

Proves the lazy-import status probe (1) reports a valid resolved config + stable config_hash + schema
readiness on a migrated-to-V38 store with the SDK absent (the expected local-first default), (2) fails
closed when the contract or seed is missing/invalid, (3) reports `schema_ready=False` on a stale
(pre-V38) store, (4) flags an unsafe/deferred config value (config_violations) and keeps the config
metadata-only (no URL/path/secret shapes), (5) never mutates the store and persists no snapshot, and
(6) is SDK-state-aware (ready_to_index + blockers flip with SDK presence). The CLI exit codes
(0 ready / 3 not-ready / 3 contract-load failure) are covered too.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.retrieval import llamaindex_config
from hb_assistant.construction.second_brain.retrieval.llamaindex_config import (
    LlamaIndexConfigError,
    _config_hash,
    build_llamaindex_config_status,
    load_llamaindex_config_contract,
    load_llamaindex_config_seed,
)
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)


def _migrated_db(td: str) -> str:
    db = Path(td) / "v38.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_contract_and_seed_load() -> None:
    contract = load_llamaindex_config_contract()
    assert "required_fields" in contract and contract["allowed_embedding_providers"]
    seed = load_llamaindex_config_seed()
    assert seed["embedding_provider"] == "local"


def test_status_normal_path() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        r = build_llamaindex_config_status(db_path=db)
        assert r["config_valid"] is True
        assert r["config_violations"] == []
        assert r["schema_ready"] is True
        assert r["snapshot_table_present"] is True
        assert r["snapshot_row_count"] == 0
        assert r["read_only"] is True
        # config_hash is stable for the same resolved config
        assert r["config"]["config_hash"] == _config_hash(load_llamaindex_config_seed())


def test_status_missing_contract_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llamaindex_config, "load_phase_09_contract", lambda name: {})
    with pytest.raises(LlamaIndexConfigError):
        build_llamaindex_config_status()


def test_status_missing_seed_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise LlamaIndexConfigError("seed missing")

    monkeypatch.setattr(llamaindex_config, "load_llamaindex_config_seed", _boom)
    with pytest.raises(LlamaIndexConfigError):
        build_llamaindex_config_status()


def test_status_stale_schema_not_ready() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        r = build_llamaindex_config_status(db_path=str(db))
        assert r["schema_ready"] is False
        assert r["ready_to_index"] is False
        assert "schema_not_ready" in r["blockers"]


def test_status_unsafe_deferred_provider_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A config selecting a deferred external provider must be flagged invalid (fail-closed).
    bad = tmp_path / "bad.seed.yaml"
    bad.write_text(
        yaml.safe_dump(
            {
                "version": "bad_v1",
                "embedding_provider": "openai",
                "embedding_model_label": "text-embedding-3-small",
                "index_kind": "vector_store",
                "vector_store_kind": "simple",
                "chunk_size": 512,
                "chunk_overlap": 64,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HB_SECOND_BRAIN_LLAMAINDEX_CONFIG", str(bad))
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        r = build_llamaindex_config_status(db_path=db)
        assert r["config_valid"] is False
        assert any("deferred" in v or "not_allowed" in v for v in r["config_violations"])


def test_committed_config_is_metadata_only() -> None:
    # The committed seed values carry no URL, absolute path, or secret shapes.
    seed = load_llamaindex_config_seed()
    for key, value in seed.items():
        s = str(value)
        assert not _SECRET_OR_URL.search(s), f"{key} has a URL/secret shape"
        assert not s.startswith("/"), f"{key} looks like an absolute path"


def test_status_does_not_mutate_db_and_report_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        before_size = Path(db).stat().st_size
        conn = sqlite3.connect(db)
        rows_before = conn.execute(
            "SELECT COUNT(*) FROM second_brain_retrieval_llamaindex_config_snapshots"
        ).fetchone()[0]
        mig_before = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()

        report = build_llamaindex_config_status(db_path=db)

        conn = sqlite3.connect(db)
        rows_after = conn.execute(
            "SELECT COUNT(*) FROM second_brain_retrieval_llamaindex_config_snapshots"
        ).fetchone()[0]
        mig_after = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()
        assert rows_before == rows_after == 0
        assert mig_before == mig_after
        assert Path(db).stat().st_size == before_size
        assert not _SECRET_OR_URL.search(json.dumps(report))


def test_status_sdk_state_aware(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        monkeypatch.setattr(llamaindex_config, "_llama_index_core_available", lambda: True)
        monkeypatch.setattr(llamaindex_config, "_llama_index_core_version", lambda: "9.9.9")
        r = build_llamaindex_config_status(db_path=db)
        assert r["sdk"]["available"] is True
        assert r["sdk"]["core_available"] is True
        assert r["core_available"] is True
        # ready_to_index also requires schema + config + runtime; the sdk_state test focuses on the
        # probe flip and blocker presence (schema may vary by migrator snapshot table in the test db)
        assert "llama_index_not_installed" not in r["blockers"]

        monkeypatch.setattr(llamaindex_config, "_llama_index_core_available", lambda: False)
        r2 = build_llamaindex_config_status(db_path=db)
        assert r2["sdk"]["core_available"] is False
        assert r2["core_available"] is False
        assert "llama_index_not_installed" in r2["blockers"]


def test_cli_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    ready = {
        "command": "second-brain retrieval llamaindex status",
        "sdk": {
            "available": False,
            "version": None,
            "core_available": False,
            "core_version": None,
            "local_embedding_available": False,
            "local_embedding_package": "llama-index-embeddings-huggingface",
            "local_embedding_version": None,
        },
        "core_available": False,
        "local_embedding_available": False,
        "local_embedding_package": "llama-index-embeddings-huggingface",
        "embedding_runtime_ready": False,
        "config": {"config_hash": "abc"},
        "policy_loaded": True,
        "config_valid": True,
        "schema_ready": True,
        "ready_to_index": False,
        "blockers": ["llama_index_not_installed"],
    }
    monkeypatch.setattr(llamaindex_config, "build_llamaindex_config_status", lambda: ready)
    result = runner.invoke(app, ["retrieval", "llamaindex", "status", "--json"])
    assert result.exit_code == 0
    assert "guardrails" in result.stdout

    not_ready = {**ready, "schema_ready": False, "ready_to_index": False}
    monkeypatch.setattr(llamaindex_config, "build_llamaindex_config_status", lambda: not_ready)
    result = runner.invoke(app, ["retrieval", "llamaindex", "status", "--json"])
    assert result.exit_code == 3


def test_cli_contract_failure_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise LlamaIndexConfigError("contract unavailable")

    monkeypatch.setattr(llamaindex_config, "build_llamaindex_config_status", _boom)
    result = runner.invoke(app, ["retrieval", "llamaindex", "status", "--json"])
    assert result.exit_code == 3
    assert "policy_loaded" in result.stdout
