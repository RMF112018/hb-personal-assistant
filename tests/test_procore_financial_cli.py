"""Phase 05 Prompt 11 — local-only financial query command tests (help + JSON shape)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_budget_projection import project_budget_family
from hb_assistant.store.procore_commitment_projection import project_commitment_family
from hb_assistant.store.procore_invoice_projection import project_invoice_family
from hb_assistant.store.procore_owner_projection import project_owner_contract_family
from hb_assistant.store.procore_rfq_change_event_projection import project_rfq_change_event_family

_NOW = "2026-05-29T00:00:00Z"
runner = CliRunner()


def _seed(db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    project_owner_contract_family(
        "prime-contracts",
        {
            "id": 1,
            "number": "PC-1",
            "status": "Approved",
            "executed": False,
            "grand_total": "1000000.00",
            "original_contract_amount": "950000.00",
            "retainage_percent": "10.00",
            "currency_configuration": {"currency_iso_code": "USD"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_owner_contract_family(
        "prime-change-orders",
        {
            "id": 7,
            "contract_id": 1,
            "number": "PCO-1",
            "status": "Pending",
            "executed": False,
            "signature_required": True,
            "grand_total": "25000.00",
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
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
        {"id": 77, "number": 12, "status": "open", "estimated_cost": "250000.00"},
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


def _patch_conn(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    import hb_assistant.store.connection as conn_mod
    import hb_assistant.store.migrator as mig_mod
    import hb_assistant.store.procore_enrichment as enr_mod
    import hb_assistant.store.procore_financials as fin_mod
    import hb_assistant.store.procore_history as hist_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(str(db))

    for mod in (conn_mod, mig_mod, enr_mod, fin_mod, hist_mod):
        monkeypatch.setattr(mod, "get_connection", _get, raising=False)


@pytest.fixture
def seeded_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "fin.sqlite"
    _seed(db)
    _patch_conn(monkeypatch, db)
    return db


_COMMANDS = ["summary", "contracts", "changes", "invoices", "budget", "risk", "coverage"]


@pytest.mark.parametrize("verb", _COMMANDS + ["financial"])
def test_financial_command_help(verb: str) -> None:
    args = ["procore", "live", "financial"] + ([] if verb == "financial" else [verb]) + ["--help"]
    res = runner.invoke(app, args)
    assert res.exit_code == 0, res.output


def test_obsidian_financial_help() -> None:
    res = runner.invoke(app, ["procore", "obsidian", "financial", "--help"])
    assert res.exit_code == 0, res.output


def test_summary_json_shape(seeded_db: Path) -> None:
    res = runner.invoke(
        app, ["procore", "live", "financial", "summary", "--project", "tropical", "--json"]
    )
    assert res.exit_code == 0, res.output
    p = json.loads(res.output)
    assert p["ok"] is True and p["project_key"] == "tropical"
    assert p["counts"]["contracts"] == 2
    assert p["counts"]["contracts_by_family"] == {"owner": 1, "commitment": 1}
    assert p["counts"]["rfqs"] == 1 and p["counts"]["change_events"] == 1
    assert p["guardrails"]["live_calls_disabled"] is True


def test_contracts_type_filter(seeded_db: Path) -> None:
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "financial",
            "contracts",
            "--project",
            "tropical",
            "--type",
            "commitment",
            "--json",
        ],
    )
    p = json.loads(res.output)
    assert p["contract_count"] == 1
    assert all(c["contract_family"] == "commitment" for c in p["contracts"])


def test_invoices_status_filter(seeded_db: Path) -> None:
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "financial",
            "invoices",
            "--project",
            "tropical",
            "--status",
            "approved",
            "--json",
        ],
    )
    p = json.loads(res.output)
    assert p["invoice_count"] == 1 and p["invoices"][0]["status"] == "approved"
    res2 = runner.invoke(
        app,
        [
            "procore",
            "live",
            "financial",
            "invoices",
            "--project",
            "tropical",
            "--status",
            "paid",
            "--json",
        ],
    )
    assert json.loads(res2.output)["invoice_count"] == 0


def test_risk_and_budget_and_changes(seeded_db: Path) -> None:
    risk = json.loads(
        runner.invoke(
            app, ["procore", "live", "financial", "risk", "--project", "tropical", "--json"]
        ).output
    )
    assert risk["ok"] is True and risk["risk_count"] >= 1  # unexecuted prime contract
    budget = json.loads(
        runner.invoke(
            app, ["procore", "live", "financial", "budget", "--project", "tropical", "--json"]
        ).output
    )
    assert budget["ok"] is True and len(budget["changes"]) == 1
    changes = json.loads(
        runner.invoke(
            app,
            [
                "procore",
                "live",
                "financial",
                "changes",
                "--project",
                "tropical",
                "--since",
                "30 days ago",
                "--json",
            ],
        ).output
    )
    assert changes["ok"] is True and "change_count" in changes


def test_coverage_detects_omitted_field(tmp_path: Path) -> None:
    payload = tmp_path / "rfq.json"
    payload.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "number": "RFQ-1",
                    "status": "open",
                    "estimated_amount": "100.00",
                    "mystery_amount": "999.99",
                }
            ]
        )
    )
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "financial",
            "coverage",
            "--project",
            "tropical",
            "--endpoint",
            "rfqs",
            "--raw-payload",
            str(payload),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    p = json.loads(res.output)
    assert p["ok"] is True
    assert "mystery_amount" in p["omitted_fields"]
    assert "estimated_amount" not in p["omitted_fields"]
