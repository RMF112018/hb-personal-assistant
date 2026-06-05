"""Tests for the Phase 06B cost / financial exposure read model + CLI."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_budget_projection import project_budget_family
from hb_assistant.store.procore_commitment_projection import project_commitment_family
from hb_assistant.store.procore_cost_exposure import build_cost_exposure
from hb_assistant.store.procore_invoice_projection import project_invoice_family
from hb_assistant.store.procore_rfq_change_event_projection import project_rfq_change_event_family

_NOW = "2026-05-29T00:00:00Z"
_CE_AMOUNT = "250000.00"  # change-event estimated_cost — must survive verbatim as a string
runner = CliRunner()

# determination language that MUST NOT appear in advisory *content* (stop condition).
# "determination" is intentionally excluded — the only occurrence is the structural
# attestation key ``determinations_made: false``; _content_blob() drops that key before scanning.
_BANNED_WORDS = (
    "liable",
    "liability",
    "entitled",
    "entitlement",
    "breach",
    "owes",
    "must pay",
    "guilty",
    "at fault",
    "negligent",
)


def _content_blob(report: dict) -> str:
    """Serialize only the human-facing content (items + note + summary), excluding the
    structural attestation keys (e.g. ``determinations_made``), then lower-case for scanning."""
    content = {
        "exposure": report.get("exposure"),
        "summary": report.get("summary"),
        "exposure_note": report.get("exposure_note"),
    }
    return json.dumps(content).lower()


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _seed(db: Path) -> None:
    project_commitment_family(
        "commitment-contracts",
        {
            "id": 2,
            "number": "SC-1",
            "status": "Pending",
            "executed": False,
            "grand_total": "500000.00",
            "vendor": {"id": 12, "name": "Acme LLC"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_invoice_family(
        "subcontractor-invoices",
        {
            "id": 40,
            "status": "approved",
            "vendor_id": 12,
            "commitment_id": 2,
            "summary": {"current_payment_due": "100000.00", "total_retainage": "5000.00"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_rfq_change_event_family(
        "rfqs",
        {
            "id": 10,
            "number": "RFQ-1",
            "status": "open",
            "estimated_amount": "50000.00",
            "commitment_contract_id": 2,
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_rfq_change_event_family(
        "change-events",
        {"id": 77, "number": 12, "status": "open", "estimated_cost": _CE_AMOUNT},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_budget_family(
        "budget-change-history",
        {
            "budget_code": "01-100",
            "column": "Revised Budget",
            "old_value": "100.00",
            "new_value": "150.00",
            "created_at": "2026-05-20",
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )


def _exp(db: Path | None, **kw):
    return build_cost_exposure("tropical", now_utc=_NOW, db_path=db, **kw)


def test_classifies_all_expected_types() -> None:
    db = _db()
    _seed(db)
    by_type = _exp(db)["summary"]["by_type"]
    # every canonical type is keyed (0 when absent)
    for t in (
        "pending_change",
        "unapproved_change",
        "budget_movement",
        "invoice_retainage_risk",
        "rfq_quote_pending",
        "compliance_risk",
        "amount_changed",
    ):
        assert t in by_type
    # the seeded fixture exercises these lenses
    assert by_type["pending_change"] >= 1  # change-event ROM / pending
    assert by_type["unapproved_change"] >= 1  # commitment_unexecuted
    assert by_type["invoice_retainage_risk"] >= 1  # approved-not-paid / payment-due / retainage
    assert by_type["rfq_quote_pending"] >= 1  # rfq cost exposure / under review
    assert by_type["amount_changed"] >= 1  # budget change from/to


def test_amounts_remain_strings() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    saw_amount = False
    for item in out["exposure"]:
        for a in item["amounts"]:
            assert isinstance(a["amount_value"], str), a
            saw_amount = True
    assert saw_amount, "expected at least one amount fact attached"
    # the distinctive change-event amount survives verbatim (no float coercion)
    assert _CE_AMOUNT in json.dumps(out)
    assert out["amounts_are_strings"] is True


def test_amount_changed_lens_has_from_to() -> None:
    db = _db()
    _seed(db)
    out = _exp(db, exposure_type="amount_changed")
    assert out["exposure"]
    names = {a["amount_name"] for it in out["exposure"] for a in it["amounts"]}
    assert names & {"from_amount", "to_amount", "adjustment_amount"}
    for it in out["exposure"]:
        assert it["source"] == "budget_change"
        assert it["signal_type"] is None


def test_type_filter() -> None:
    db = _db()
    _seed(db)
    out = _exp(db, exposure_type="rfq_quote_pending")
    assert out["exposure"]
    assert all(it["exposure_type"] == "rfq_quote_pending" for it in out["exposure"])


def test_importance_filter() -> None:
    db = _db()
    _seed(db)
    out = _exp(db, importance="high")
    assert all(it["importance"] == "high" for it in out["exposure"])
    # amount_changed (medium) is excluded under a high filter
    assert all(it["exposure_type"] != "amount_changed" for it in out["exposure"])


def test_review_required_high_sensitivity() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    sensitive = [
        it
        for it in out["exposure"]
        if it["exposure_type"] in ("compliance_risk", "unapproved_change", "invoice_retainage_risk")
    ]
    assert sensitive
    for it in sensitive:
        assert it["review_required"] is True
        assert "review_required_high_sensitivity" in it["reason_codes"]
    assert out["summary"]["review_required"] >= 1


def test_no_determination_language() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    blob = _content_blob(out)
    for word in _BANNED_WORDS:
        assert word not in blob, f"determination word leaked: {word}"
    assert out["determinations_made"] is False
    assert out["no_raw_values_persisted"] is True
    assert out["no_live_call_performed"] is True


def test_ordering_high_first() -> None:
    db = _db()
    _seed(db)
    items = _exp(db)["exposure"]
    ranks = {"high": 0, "medium": 1, "low": 2}
    seq = [ranks.get(it["importance"], 3) for it in items]
    assert seq == sorted(seq)


def test_empty_project() -> None:
    db = _db()
    out = _exp(db)
    assert out["summary"]["total"] == 0
    assert out["exposure"] == []
    assert out["summary"]["by_type"]["pending_change"] == 0


def _patch_conn(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    import hb_assistant.store.connection as conn_mod
    import hb_assistant.store.migrator as mig_mod
    import hb_assistant.store.procore_cost_exposure as exp_mod
    import hb_assistant.store.procore_enrichment as enr_mod
    import hb_assistant.store.procore_financials as fin_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(str(db))

    for mod in (conn_mod, mig_mod, enr_mod, fin_mod, exp_mod):
        monkeypatch.setattr(mod, "get_connection", _get, raising=False)


def test_cli_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "exp.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app,
        ["procore", "live", "financial", "exposure", "--project", "tropical", "--json"],
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
        "filters",
        "summary",
        "exposure",
        "exposure_truncated",
        "amounts_are_strings",
        "no_live_call_performed",
        "no_raw_values_persisted",
        "determinations_made",
        "guardrails",
    ):
        assert key in payload, f"missing {key}"
    assert payload["ok"] is True
    assert payload["determinations_made"] is False
    blob = _content_blob(payload)
    for word in _BANNED_WORDS:
        assert word not in blob, f"determination word leaked: {word}"
