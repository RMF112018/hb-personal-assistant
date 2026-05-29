"""Phase 05 — generalized N+1 parent->child orchestration (offline, fake transport).

Drives `run_live_sync` for a financial child endpoint with a path-aware synthetic
transport (parent list on the parent path, child pages on the per-parent child path) and
an in-memory adapter promotion. Proves: parent list fetched, one child GET per parent,
children upserted with the correct parent_procore_id, the financial projection ran, and a
per-parent child transport error is captured without aborting the run.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore import endpoints as ep_registry
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.store.migrator import SQLiteMigrator

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _rows(db: Path, table: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table}").fetchall()
    finally:
        conn.close()


class _FakeResponse:
    def __init__(self, body: Any):
        self._body = body
        self.status_code = 200
        self.headers: Dict[str, str] = {}
        self.text = ""

    def json(self) -> Any:
        return self._body


class _PathAwareTransport:
    """Parent list on `/commitment_contracts`; line items on
    `/commitment_contracts/{id}/line_items`. Parent 503's child GET raises (per-parent
    error path). Pagination halts after page 1."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append(url)
        page = int((params or {}).get("page", 1))
        if url.rstrip("/").endswith("/commitment_contracts"):  # parent list
            return _FakeResponse({"data": [{"id": 501}, {"id": 502}, {"id": 503}]} if page == 1 else {"data": []})
        if "/commitment_contracts/503/line_items" in url:  # per-parent error path
            raise RuntimeError("synthetic child transport failure")
        if url.endswith("/line_items"):  # child line items
            pid = url.split("/commitment_contracts/")[1].split("/")[0]
            if page != 1:
                return _FakeResponse({"data": []})
            return _FakeResponse({"data": [
                {"id": int(pid) * 10 + 1, "amount": "100.00",
                 "wbs_code": {"id": 3, "flat_code": "01-100"}},
                {"id": int(pid) * 10 + 2, "amount": "200.00"},
            ]})
        return _FakeResponse({"data": []})


class _ReqItemsTransport:
    """v1.0 requisition contract-items: parent list on `/requisitions`, items on
    `/requisitions/{id}/contract_items` — the child GET MUST carry ?project_id."""

    def __init__(self) -> None:
        self.child_params: List[Dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        page = int((params or {}).get("page", 1))
        if "/contract_items" in url:
            self.child_params.append(dict(params or {}))
            pid = url.split("/requisitions/")[1].split("/")[0]
            if page != 1:
                return _FakeResponse([])
            return _FakeResponse([
                {"id": int(pid) * 10 + 1, "item_type": "contract_detail_item",
                 "cost_code_id": 21585118, "line_item_id": 3129856,
                 "description_of_work": "Install windows", "scheduled_value": "1.00",
                 "work_completed_this_period": "0.00", "materials_presently_stored": "2691.36",
                 "subcontractor_claimed_amount": "0.0",
                 "work_completed_retainage_retained_this_period": "12.50",
                 "wbs_code": {"id": 999, "flat_code": "01-011.CT1", "description": "Eng.CT1"},
                 "currency_configuration": {"currency_iso_code": "USD"},
                 "comment": "Installation charges", "status": "no_action", "position": 1},
            ])
        if url.rstrip("/").endswith("/requisitions"):  # parent list (v1.1, array)
            return _FakeResponse([{"id": 58820}, {"id": 58821}] if page == 1 else [])
        return _FakeResponse([])


class _RfqQuotesTransport:
    """rfq quotes: parent list on `/rfqs`, quotes on `/rfqs/{id}/quotes` — the child GET
    MUST carry both `project_id` and `contract_id` (the rfq's commitment_contract_id)."""

    def __init__(self) -> None:
        self.child_params: List[Dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        page = int((params or {}).get("page", 1))
        if "/quotes" in url:
            self.child_params.append(dict(params or {}))
            if page != 1:
                return _FakeResponse([])
            return _FakeResponse([
                {"id": 105445, "cost": "4500.0", "schedule_impact": 2,
                 "description": "Need to destroy some roofing.", "request_for_quote_id": 136264,
                 "created_by": {"id": 160586, "login": "carl@example.com", "name": "Carl"},
                 "attachments": [{"id": 42, "name": "f.ext",
                                  "url": "https://storage.procore.com/x?sig=SECRETSIG"}]},
            ])
        if url.rstrip("/").endswith("/rfqs"):  # parent list (array)
            return _FakeResponse([{"id": 136264, "commitment_contract_id": 701973}] if page == 1 else [])
        return _FakeResponse([])


def _promote(monkeypatch: pytest.MonkeyPatch, endpoint_id: str) -> None:
    base = ep_registry.get(endpoint_id)
    assert base is not None
    monkeypatch.setitem(ep_registry._BY_ID, endpoint_id, replace(base, live_verified=True))


def test_commitment_line_items_n1_fetch_projects_with_parent_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    _promote(monkeypatch, "commitment-line-items")
    db = _db()
    transport = _PathAwareTransport()

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="commitment-line-items",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=50,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] in ("success", "partial_success")
    # one parent-list GET + one child GET per parent (incl. the failing 503)
    assert any(u.rstrip("/").endswith("/commitment_contracts") for u in transport.calls)
    assert sum("/line_items" in u for u in transport.calls) == 3
    # children upserted with the correct parent_procore_id (501/502; 503 errored)
    live = [r for r in _rows(db, "procore_live_records") if r["endpoint_id"] == "commitment-line-items"]
    assert len(live) == 4  # 2 parents x 2 line items
    assert {r["parent_procore_id"] for r in live} == {"501", "502"}
    # the financial projection ran (commitment line items + amount facts)
    li = _rows(db, "procore_financial_line_items")
    assert len(li) == 4 and all(r["line_item_kind"] == "commitment" for r in li)
    assert any(r["amount"] == "100.00" for r in li)
    assert _rows(db, "procore_financial_amount_facts")
    # the reserved parent-id key never leaked into the persisted canonical fields
    assert all("_hb_parent_procore_id" not in (r["canonical_json_redacted"] or "") for r in live)
    # per-parent child transport error captured, run not aborted
    assert receipt["projection_error_count"] == 0
    assert any("detail_transport_error" in e for e in receipt["redacted_errors"])


def test_v1_child_get_carries_project_id_query_param(monkeypatch: pytest.MonkeyPatch) -> None:
    # v1.0 requisition children carry no {project_id} path segment -> the N+1 child GET must
    # send project_id as a query param (else Procore 404s, as observed live).
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    _promote(monkeypatch, "subcontractor-invoice-contract-items")
    db = _db()
    transport = _ReqItemsTransport()

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="subcontractor-invoice-contract-items",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=50,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] in ("success", "partial_success")
    # every child GET carried project_id
    assert transport.child_params and all("project_id" in p for p in transport.child_params)
    # children upserted with the requisition id as parent + projected into invoice items
    live = [r for r in _rows(db, "procore_live_records")
            if r["endpoint_id"] == "subcontractor-invoice-contract-items"]
    assert len(live) == 2 and {r["parent_procore_id"] for r in live} == {"58820", "58821"}
    items = _rows(db, "procore_financial_invoice_items")
    assert len(items) == 2
    assert all(r["item_type"] == "contract_detail_item" for r in items)
    assert any(r["retainage_held"] == "12.50" for r in items)  # work_completed_retainage_*
    assert all(r["raw_body_persisted"] == 0 for r in items)


def test_rfq_quote_child_get_carries_project_id_and_contract_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # rfq quotes require contract_id (= the rfq's commitment_contract_id) AND project_id.
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    _promote(monkeypatch, "rfq-quotes")
    db = _db()
    transport = _RfqQuotesTransport()

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfq-quotes",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=50,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] in ("success", "partial_success")
    # the child GET carried project_id AND contract_id (= parent rfq's commitment_contract_id)
    assert transport.child_params
    assert all("project_id" in p and p.get("contract_id") == "701973" for p in transport.child_params)
    # quote amount fact + quote_of edge; signed-URL attachment never persisted raw
    facts = {f["amount_name"]: f["amount_value"] for f in _rows(db, "procore_financial_amount_facts")}
    assert facts.get("cost") == "4500.0"
    edges = {(e["edge_type"], e["to_record_key"]) for e in _rows(db, "procore_record_edges")}
    assert ("quote_of", "tropical|rfqs||136264") in edges
    blob = "|".join(
        "" if c is None else str(c) for r in _rows(db, "procore_live_records") for c in r
    )
    assert "SECRETSIG" not in blob and "sig=" not in blob
