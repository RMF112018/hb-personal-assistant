"""Tests for the Phase 06B no-writeback / no-secret / no-raw-body proof (Prompt 15)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_no_writeback_proof import (
    _scan_text_for_secrets,
    build_no_writeback_proof,
)

_NOW = "2026-05-29T00:00:00Z"
runner = CliRunner()


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _seed_record(db: Path) -> None:
    conn = get_connection(str(db))
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        """INSERT INTO procore_live_records (project_key, procore_project_id, endpoint_id,
           parent_procore_id, procore_record_id, canonical_json_redacted, review_required,
           first_seen_at_utc, last_seen_at_utc, last_sync_run_id, raw_body_persisted)
           VALUES ('tropical','P1','rfis','','1','{}',0,?,?,'run-1',0)""",
        (_NOW, _NOW),
    )
    conn.commit()


# --- the proof passes against repo truth ---


def test_proof_passes_all_checks() -> None:
    db = _db()
    _seed_record(db)
    out = build_no_writeback_proof(now_utc=_NOW, db_path=db)
    assert out["proof_passed"] is True, out["checks_detail"]
    for name, c in out["checks_detail"].items():
        assert c["passed"] is True, f"{name}: {c['findings']}"
        assert c["findings"] == [] or name == "evidence_output_scan"
    assert out["checks"]["no_m365_writeback"] is True
    assert out["checks"]["no_procore_writeback"] is True
    assert out["checks"]["no_raw_bodies_persisted"] is True
    assert out["determinations_made"] is False
    assert len(out["scanned_modules"]) >= 7


# --- raw-body guardrail probe ---


def test_raw_body_guardrail_reports_zero_only() -> None:
    db = _db()
    _seed_record(db)
    out = build_no_writeback_proof(now_utc=_NOW, db_path=db)
    tables = {t["table"]: t for t in out["raw_body_tables"]}
    assert "procore_live_records" in tables
    lr = tables["procore_live_records"]
    assert lr["has_check"] is True
    assert lr["distinct_values"] in ([0], [])  # only 0 (or empty when no rows)
    assert all(t["has_check"] for t in out["raw_body_tables"])


def test_raw_body_check_constraint_bites() -> None:
    db = _db()
    conn = get_connection(str(db))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO procore_live_records (project_key, procore_project_id, endpoint_id,
               parent_procore_id, procore_record_id, canonical_json_redacted, review_required,
               first_seen_at_utc, last_seen_at_utc, last_sync_run_id, raw_body_persisted)
               VALUES ('tropical','P1','rfis','','9','{}',0,?,?,'run-1',1)""",
            (_NOW, _NOW),
        )


# --- the scanner is not vacuous ---


def test_secret_scanner_flags_planted_secrets() -> None:
    assert _scan_text_for_secrets("Authorization: Bearer abcdef0123456789ABCDEF0123")
    assert _scan_text_for_secrets("-----BEGIN RSA PRIVATE KEY-----")
    assert _scan_text_for_secrets(
        "https://x.blob.core.windows.net/c/f?sv=2021-08-06&sig=AbCd12+/EfGh34iJ"
    )
    assert _scan_text_for_secrets('"refresh_token": "0.AAAAverylongtokenvalue"')


def test_secret_scanner_ignores_prose() -> None:
    # evidence narratives mention these words without carrying a real secret
    assert (
        _scan_text_for_secrets("No tokens, Authorization headers, or signed URLs are emitted.")
        == []
    )
    assert _scan_text_for_secrets("client_secret is never logged or committed.") == []


# --- CLI ---


def _patch_conn(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    import hb_assistant.store.connection as conn_mod
    import hb_assistant.store.migrator as mig_mod
    import hb_assistant.store.procore_no_writeback_proof as nwb_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(str(db))

    for mod in (conn_mod, mig_mod, nwb_mod):
        monkeypatch.setattr(mod, "get_connection", _get, raising=False)


def test_cli_proof_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "nwb.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app, ["procore", "live", "no-writeback-proof", "--json"], catch_exceptions=False
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in (
        "command",
        "ok",
        "phase",
        "proof_passed",
        "checks",
        "checks_detail",
        "scanned_modules",
        "raw_body_tables",
        "query_commands",
        "note",
        "determinations_made",
        "guardrails",
    ):
        assert key in payload, f"missing {key}"
    assert payload["proof_passed"] is True
    assert payload["ok"] is True
    assert payload["checks"]["no_procore_writeback"] is True
    assert "project-health" in payload["query_commands"]
    assert payload["determinations_made"] is False
