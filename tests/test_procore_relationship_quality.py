"""Tests for the Phase 06B responsible-party & relationship-quality diagnostics + CLI."""

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
from hb_assistant.store.procore_enrichment import emit_record_edge
from hb_assistant.store.procore_relationship_quality import (
    build_relationship_quality,
    build_responsible_party_gaps,
)

_NOW = "2026-05-29T00:00:00Z"
runner = CliRunner()

# data-quality diagnostics must not drift into legal/claims determination language (stop condition).
_BANNED_WORDS = (
    "liable",
    "liability",
    "entitled",
    "entitlement",
    "breach",
    "owes",
    "must pay",
    "at fault",
    "negligent",
    "guilty",
    "responsible for the delay",
)


def _content_blob(report: dict) -> str:
    """Serialize human-facing content only, excluding structural attestation keys, lower-cased."""
    content = {
        k: report.get(k)
        for k in (
            "coverage",
            "summary",
            "orphans",
            "linkage",
            "duplicate_warnings",
            "relationship_edge_map",
        )
    }
    return json.dumps(content).lower()


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


def _edge(db: Path, *, rk: str, edge_type: str, endpoint_id: str) -> None:
    emit_record_edge(
        project_key="tropical",
        from_record_key=rk,
        edge_type=edge_type,
        source_endpoint_id=endpoint_id,
        to_entity_key="entity-x",
        now_utc=_NOW,
        db_path=db,
    )


def _contract(db: Path, *, endpoint_id: str, contract_id: str, family: str) -> None:
    conn = get_connection(str(db))
    conn.execute(
        """INSERT INTO procore_financial_contracts (record_key, project_key, endpoint_id,
           contract_id, contract_family) VALUES (?,?,?,?,?)""",
        (
            "|".join(["tropical", endpoint_id, "", contract_id]),
            "tropical",
            endpoint_id,
            contract_id,
            family,
        ),
    )
    conn.commit()


def _gaps(db: Path, **kw):
    return build_responsible_party_gaps("tropical", now_utc=_NOW, db_path=db, **kw)


def _quality(db: Path, **kw):
    return build_relationship_quality("tropical", now_utc=_NOW, db_path=db, **kw)


# --- responsible-party-gaps ---


def test_partial_gap_when_some_records_carry_edge() -> None:
    db = _db()
    rk1 = _record(db, endpoint_id="rfis", record_id="1")
    _record(db, endpoint_id="rfis", record_id="2")  # no assignee edge
    _edge(db, rk=rk1, edge_type="assignee", endpoint_id="rfis")
    cov = {c["relationship"]: c for c in _gaps(db)["coverage"] if c["endpoint_id"] == "rfis"}
    assert cov["assignee"]["status"] == "partial_gap"
    assert cov["assignee"]["records"] == 2
    assert cov["assignee"]["records_with_edge"] == 1
    assert cov["assignee"]["missing"] == 1
    assert cov["assignee"]["coverage_pct"] == 50.0


def test_covered_when_all_records_carry_edge() -> None:
    db = _db()
    rk = _record(db, endpoint_id="rfis", record_id="1")
    _edge(db, rk=rk, edge_type="created_by", endpoint_id="rfis")
    cov = {c["relationship"]: c for c in _gaps(db)["coverage"] if c["endpoint_id"] == "rfis"}
    assert cov["owner"]["status"] == "covered"  # owner -> created_by
    assert cov["owner"]["missing"] == 0


def test_not_observed_when_no_record_carries_edge() -> None:
    db = _db()
    _record(db, endpoint_id="rfis", record_id="1")
    cov = {c["relationship"]: c for c in _gaps(db)["coverage"] if c["endpoint_id"] == "rfis"}
    # nothing carries vendor -> reported not_observed, NOT a fabricated 100% gap
    assert cov["vendor"]["status"] == "not_observed"
    assert cov["vendor"]["missing"] == 1  # records - 0, but classified not_observed
    assert _gaps(db)["summary"]["partial_gap_relationships"] == 0


def test_endpoint_isolation_and_filter() -> None:
    db = _db()
    rk = _record(db, endpoint_id="rfis", record_id="1")
    _edge(db, rk=rk, edge_type="vendor", endpoint_id="rfis")
    _record(db, endpoint_id="submittals", record_id="2")
    out = _gaps(db, endpoint_id="rfis")
    assert {c["endpoint_id"] for c in out["coverage"]} == {"rfis"}
    assert out["summary"]["endpoints"] == 1


def test_all_six_relationships_keyed() -> None:
    db = _db()
    _record(db, endpoint_id="rfis", record_id="1")
    rels = {c["relationship"] for c in _gaps(db)["coverage"]}
    assert rels == {
        "owner",
        "assignee",
        "ball_in_court",
        "responsible_contractor",
        "vendor",
        "location",
    }


# --- relationship-quality ---


def test_orphan_child_detected() -> None:
    db = _db()
    _record(db, endpoint_id="meetings", record_id="100")  # parent exists
    _record(db, endpoint_id="meeting-topics", record_id="200", parent="100")  # resolves
    _record(db, endpoint_id="meeting-topics", record_id="201", parent="999")  # orphan
    out = _quality(db)
    assert out["orphans"]["orphan_count"] == 1
    assert out["orphans"]["by_endpoint"] == {"meeting-topics": 1}
    sample = out["orphans"]["sample"][0]
    assert sample["parent_procore_id"] == "999"
    assert out["linkage"]["child_records"] == 2
    assert out["linkage"]["children_with_resolved_parent"] == 1
    assert out["linkage"]["linkage_pct"] == 50.0
    assert out["linkage"]["linkage_status"] == "partial"


def test_linkage_unknown_when_no_children() -> None:
    db = _db()
    _record(db, endpoint_id="rfis", record_id="1")
    out = _quality(db)
    assert out["linkage"]["linkage_status"] == "unknown"
    assert out["linkage"]["linkage_pct"] is None
    assert out["orphans"]["orphan_count"] == 0


def test_complete_linkage() -> None:
    db = _db()
    _record(db, endpoint_id="meetings", record_id="100")
    _record(db, endpoint_id="meeting-topics", record_id="200", parent="100")
    out = _quality(db)
    assert out["linkage"]["linkage_status"] == "complete"
    assert out["linkage"]["linkage_pct"] == 100.0


def test_duplicate_po_commitment_warning() -> None:
    db = _db()
    _contract(db, endpoint_id="commitment-contracts", contract_id="55", family="commitment")
    _contract(db, endpoint_id="purchase-order-contracts", contract_id="55", family="purchase_order")
    _contract(db, endpoint_id="purchase-order-contracts", contract_id="56", family="purchase_order")
    out = _quality(db)
    warns = out["duplicate_warnings"]
    assert len(warns) == 1
    assert warns[0]["contract_id"] == "55"
    assert warns[0]["duplicate_of"] == "commitment"
    assert out["summary"]["duplicate_warnings"] == 1


# --- guardrails / CLI ---


def test_no_determination_language() -> None:
    db = _db()
    rk = _record(db, endpoint_id="rfis", record_id="1")
    _edge(db, rk=rk, edge_type="assignee", endpoint_id="rfis")
    _record(db, endpoint_id="meeting-topics", record_id="2", parent="999")
    for report in (_gaps(db), _quality(db)):
        blob = _content_blob(report)
        for word in _BANNED_WORDS:
            assert word not in blob, f"determination word leaked: {word}"
        assert report["determinations_made"] is False
        assert report["no_raw_values_persisted"] is True
        assert report["no_live_call_performed"] is True


def test_empty_project() -> None:
    db = _db()
    g, q = _gaps(db), _quality(db)
    assert g["coverage"] == [] and g["summary"]["endpoints"] == 0
    assert q["summary"]["total_records"] == 0
    assert q["linkage"]["linkage_status"] == "unknown"


def _patch_conn(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    import hb_assistant.store.connection as conn_mod
    import hb_assistant.store.migrator as mig_mod
    import hb_assistant.store.procore_commitment_projection as com_mod
    import hb_assistant.store.procore_relationship_quality as rq_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(str(db))

    for mod in (conn_mod, mig_mod, com_mod, rq_mod):
        monkeypatch.setattr(mod, "get_connection", _get, raising=False)


def test_cli_responsible_party_gaps_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "rq.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    rk = _record(db, endpoint_id="rfis", record_id="1")
    _edge(db, rk=rk, edge_type="assignee", endpoint_id="rfis")
    _record(db, endpoint_id="rfis", record_id="2")
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app,
        ["procore", "live", "responsible-party-gaps", "--project", "tropical", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in (
        "command",
        "ok",
        "phase",
        "project_key",
        "generated_at",
        "summary",
        "coverage",
        "relationship_edge_map",
        "no_live_call_performed",
        "no_raw_values_persisted",
        "determinations_made",
        "guardrails",
    ):
        assert key in payload, f"missing {key}"
    assert payload["ok"] is True
    assert payload["determinations_made"] is False


def test_cli_relationship_quality_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "rq2.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _record(db, endpoint_id="meetings", record_id="100")
    _record(db, endpoint_id="meeting-topics", record_id="201", parent="999")
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app,
        ["procore", "live", "relationship-quality", "--project", "tropical", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in (
        "command",
        "ok",
        "phase",
        "summary",
        "orphans",
        "linkage",
        "duplicate_warnings",
        "no_live_call_performed",
        "no_raw_values_persisted",
        "determinations_made",
        "guardrails",
    ):
        assert key in payload, f"missing {key}"
    assert payload["orphans"]["orphan_count"] == 1
    assert payload["determinations_made"] is False
