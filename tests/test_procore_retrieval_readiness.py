"""Tests for the Phase 06B retrieval fact manifest (Prompt 14)."""

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
from hb_assistant.store.procore_enrichment import emit_action_signal
from hb_assistant.store.procore_operational import build_retrieval_readiness

_NOW = "2026-05-29T00:00:00Z"
_PAST = "2026-05-01T00:00:00Z"
_SECRET_TITLE = "ZZSENSITIVERECORDZZ"
runner = CliRunner()

# field names / tokens that must NEVER appear in a retrieval-safe manifest.
_FORBIDDEN = (
    "canonical_json", "old_value_redacted", "new_value_redacted", "old_value_hash",
    "new_value_hash", "body", "description", "notes", "remarks", "raw_body",
    "bearer ", "authorization", "refresh_token", "client_secret", "-----begin", "?sv=", "sig=",
)


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _record(db: Path, *, endpoint_id: str, record_id: str, title: str = "",
            review: bool = False) -> str:
    conn = get_connection(str(db))
    conn.execute("PRAGMA foreign_keys=OFF")  # test seed: skip the sync-run FK (throwaway DB)
    conn.execute(
        """INSERT INTO procore_live_records (project_key, procore_project_id, endpoint_id,
           parent_procore_id, procore_record_id, procore_record_number, title_redacted, status,
           updated_at_utc, canonical_json_redacted, review_required, first_seen_at_utc,
           last_seen_at_utc, last_sync_run_id, raw_body_persisted)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
        ("tropical", "P1", endpoint_id, "", record_id, f"N-{record_id}", title, "open", _NOW,
         '{"description": "RAWFREETEXTLEAK"}', 1 if review else 0, _NOW, _NOW, "run-1"),
    )
    conn.commit()
    return "|".join(["tropical", endpoint_id, "", record_id])


def _amount(db: Path, *, record_key: str, endpoint_id: str, name: str, value: str) -> None:
    conn = get_connection(str(db))
    conn.execute(
        """INSERT INTO procore_financial_amount_facts (amount_fact_id, project_key, record_key,
           endpoint_id, amount_name, amount_value, currency_iso_code, source_field_path,
           created_at_utc)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (f"af-{record_key}-{name}", "tropical", record_key, endpoint_id, name, value, "USD", name,
         _NOW),
    )
    conn.commit()


def _seed(db: Path) -> None:
    r1 = _record(db, endpoint_id="rfis", record_id="1", title="rfi-one")
    emit_action_signal(project_key="tropical", record_key=r1, endpoint_id="rfis",
                       signal_type="rfi_overdue", importance="high", due_at_utc=_PAST,
                       now_utc=_NOW, db_path=db)
    c1 = _record(db, endpoint_id="commitment-contracts", record_id="55", title="sc-1")
    _amount(db, record_key=c1, endpoint_id="commitment-contracts", name="grand_total",
            value="250000.00")
    # a review-flagged record must be blocked (never emitted as a fact)
    _record(db, endpoint_id="rfis", record_id="9", title=_SECRET_TITLE, review=True)


def _m(db: Path, **kw):
    return build_retrieval_readiness("tropical", now_utc=_NOW, db_path=db, **kw)


def test_manifest_families_and_counts() -> None:
    db = _db()
    _seed(db)
    out = _m(db)
    man = out["manifest"]
    bt = man["by_fact_type"]
    assert bt["record"] == 2          # rfi-1 + commitment (review-flagged excluded)
    assert bt["action_signal"] == 1
    assert bt["amount"] == 1
    assert man["total_facts"] == sum(bt.values())
    assert "rfis" in man["by_endpoint"]
    # every fact is source-linked to table/key/record
    for f in man["samples"]:
        assert f["source_link"] and f["source_key"]
        assert "fact_type" in f and "source_table" in f


def test_review_required_blocked() -> None:
    db = _db()
    _seed(db)
    out = _m(db)
    assert out["manifest"]["review_required_blocked"] == 1
    assert out["manifest"]["blocked_by_reason"]["review_required"] == 1
    # the review-flagged record's title is never emitted
    assert _SECRET_TITLE not in json.dumps(out)


def test_samples_capped() -> None:
    db = _db()
    _seed(db)
    out = _m(db, max_samples=1)
    assert len(out["manifest"]["samples"]) == 1
    assert out["manifest"]["samples_truncated"] is True


def test_amount_values_are_strings() -> None:
    db = _db()
    _seed(db)
    out = _m(db)
    amounts = [f for f in out["manifest"]["samples"] if f["fact_type"] == "amount"]
    assert amounts
    for f in amounts:
        assert isinstance(f["attributes"]["amount_value"], str)
    assert "250000.00" in json.dumps(out)


def test_no_forbidden_field_leakage() -> None:
    db = _db()
    _seed(db)
    blob = json.dumps(_m(db)).lower()
    leaked = [w for w in _FORBIDDEN if w in blob]
    assert not leaked, f"forbidden content leaked: {leaked}"
    assert "rawfreetextleak" not in blob  # canonical_json free text never read


def test_corpus_preserved_and_not_ready_without_text() -> None:
    db = _db()
    _seed(db)
    out = _m(db)
    assert out["retrieval_ready"] is False  # no text-intelligence rows seeded
    assert "no_text_intelligence_rows" in out["reasons"]
    assert out["corpus"]["live_records"] == 3  # total records incl. the review-flagged one
    assert out["determinations_made"] is False


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


def test_cli_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "rr.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app, ["procore", "live", "retrieval-ready", "--project", "tropical", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in ("command", "ok", "phase", "retrieval_ready", "reasons", "corpus", "manifest",
                "note", "determinations_made", "guardrails"):
        assert key in payload, f"missing {key}"
    assert payload["manifest"]["total_facts"] >= 1
    assert payload["determinations_made"] is False
    leaked = [w for w in _FORBIDDEN if w in json.dumps(payload).lower()]
    assert not leaked, leaked
