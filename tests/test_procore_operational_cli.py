"""Tests for the Phase 06B operational CLI surface (Prompt 12).

Help-text, JSON-shape, and failure-mode tests for the four new operator verbs, plus a static
guarantee that the Phase 06B query read-model modules never import a Procore HTTP client.
"""

from __future__ import annotations

import ast
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_enrichment import emit_action_signal

_NOW = "2026-05-29T00:00:00Z"
_PAST = "2026-05-01T00:00:00Z"
runner = CliRunner()

_NEW_COMMANDS = ("digest", "risks", "retrieval-ready", "no-writeback-proof")


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _record(db: Path, *, endpoint_id: str, record_id: str, parent: str = "") -> str:
    conn = get_connection(str(db))
    conn.execute("PRAGMA foreign_keys=OFF")  # test seed: skip the sync-run FK (throwaway DB)
    conn.execute(
        """INSERT INTO procore_live_records (project_key, procore_project_id, endpoint_id,
           parent_procore_id, procore_record_id, canonical_json_redacted, review_required,
           first_seen_at_utc, last_seen_at_utc, last_sync_run_id, raw_body_persisted)
           VALUES (?,?,?,?,?,?,0,?,?,?,0)""",
        ("tropical", "P1", endpoint_id, parent, record_id, "{}", _NOW, _NOW, "run-1"),
    )
    conn.commit()
    return "|".join(["tropical", endpoint_id, parent, record_id])


def _seed(db: Path) -> None:
    rk = _record(db, endpoint_id="rfis", record_id="1")
    emit_action_signal(project_key="tropical", record_key=rk, endpoint_id="rfis",
                       signal_type="rfi_overdue", importance="high", due_at_utc=_PAST,
                       now_utc=_NOW, db_path=db)


def _patch_conn(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    import hb_assistant.store.connection as conn_mod
    import hb_assistant.store.migrator as mig_mod
    import hb_assistant.store.procore_action_queue as aq_mod
    import hb_assistant.store.procore_commitment_projection as com_mod
    import hb_assistant.store.procore_cost_exposure as ce_mod
    import hb_assistant.store.procore_enrichment as enr_mod
    import hb_assistant.store.procore_financials as fin_mod
    import hb_assistant.store.procore_history as hist_mod
    import hb_assistant.store.procore_operational as op_mod
    import hb_assistant.store.procore_project_health as ph_mod
    import hb_assistant.store.procore_relationship_quality as rq_mod
    import hb_assistant.store.procore_schedule_exposure as se_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(str(db))

    for mod in (conn_mod, mig_mod, enr_mod, fin_mod, hist_mod, aq_mod, ce_mod, se_mod, ph_mod,
                rq_mod, com_mod, op_mod):
        monkeypatch.setattr(mod, "get_connection", _get, raising=False)


def _invoke(args: list[str]):
    return runner.invoke(app, args, catch_exceptions=False)


# --- help tests (local-only / read-only must be stated) ---

@pytest.mark.parametrize("command", _NEW_COMMANDS)
def test_help_states_local_and_read_only(command: str) -> None:
    res = _invoke(["procore", "live", command, "--help"])
    assert res.exit_code == 0, res.output
    out = res.output.lower()
    assert "local" in out, res.output
    assert "read-only" in out, res.output


# --- JSON-shape tests ---

def test_digest_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "d.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    res = _invoke(["procore", "live", "digest", "--project", "tropical", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in ("command", "ok", "phase", "project_key", "generated_at", "health_status",
                "headline", "sources", "no_live_call_performed", "determinations_made", "guardrails"):
        assert key in payload, f"missing {key}"
    assert payload["headline"]["overdue"] >= 1
    assert payload["determinations_made"] is False


def test_risks_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "r.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    res = _invoke(["procore", "live", "risks", "--project", "tropical", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in ("command", "ok", "phase", "summary", "risks", "risks_truncated",
                "determinations_made", "guardrails"):
        assert key in payload, f"missing {key}"
    assert payload["summary"]["high_importance"] >= 1
    assert any(r["signal_type"] == "rfi_overdue" for r in payload["risks"])


def test_retrieval_ready_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "rr.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    res = _invoke(["procore", "live", "retrieval-ready", "--project", "tropical", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in ("command", "ok", "retrieval_ready", "reasons", "corpus", "note",
                "determinations_made", "guardrails"):
        assert key in payload, f"missing {key}"
    # seeded a live record but no text-intelligence -> not ready, reason recorded
    assert payload["retrieval_ready"] is False
    assert "no_text_intelligence_rows" in payload["reasons"]
    assert payload["corpus"]["live_records"] == 1


def test_no_writeback_proof_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "nw.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _patch_conn(monkeypatch, db)
    res = _invoke(["procore", "live", "no-writeback-proof", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in ("command", "ok", "checks", "query_commands", "note", "guardrails"):
        assert key in payload, f"missing {key}"
    assert payload["checks"]["no_m365_writeback"] is True
    assert payload["checks"]["no_procore_writeback"] is True
    assert "project-health" in payload["query_commands"]
    assert payload["project_key"] is None  # optional, omitted


# --- failure-mode tests ---

@pytest.mark.parametrize("command", ("digest", "risks", "retrieval-ready"))
def test_missing_project_fails(command: str) -> None:
    res = runner.invoke(app, ["procore", "live", command, "--json"])
    assert res.exit_code != 0  # Typer usage error for the required --project


def test_empty_project_is_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "empty.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _patch_conn(monkeypatch, db)
    res = _invoke(["procore", "live", "digest", "--project", "ghost", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["headline"]["total_records"] == 0


# --- static no-HTTP-client proof for the query read-model modules ---

_FORBIDDEN = {"requests", "httpx", "urllib3", "urllib.request",
              "hb_assistant.procore.http_client"}
_QUERY_MODULES = (
    "procore_operational", "procore_project_health", "procore_freshness", "procore_action_queue",
    "procore_cost_exposure", "procore_schedule_exposure", "procore_relationship_quality",
)


def _forbidden(name: str) -> bool:
    return name in _FORBIDDEN or any(name.startswith(f"{m}.") for m in _FORBIDDEN)


def test_query_models_do_not_import_http_client() -> None:
    src = Path(__file__).resolve().parent.parent / "src" / "hb_assistant" / "store"
    violations: list[str] = []
    for mod in _QUERY_MODULES:
        tree = ast.parse((src / f"{mod}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _forbidden(alias.name):
                        violations.append(f"{mod}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and _forbidden(node.module or ""):
                violations.append(f"{mod}: from {node.module} import ...")
    assert not violations, "query read-model modules must not import an HTTP client: " + str(violations)
