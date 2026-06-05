"""Phase 05 Prompt 10 — live-sync dispatch chain, idempotency, projection isolation.

Drives ``run_live_sync`` end-to-end for a financial endpoint with a synthetic
transport (no live traffic) by temporarily promoting the adapter to
``live_verified=True`` in-memory. Proves the full chain (normalize -> latest-state
upsert -> history -> financial projection), idempotent re-sync, and that a projection
failure is captured in the receipt WITHOUT breaking the latest-state upsert.
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
        self._json_body = body
        self.status_code = 200
        self.headers: Dict[str, str] = {}
        self.text = ""

    def json(self) -> Any:
        return self._json_body


class _FakeTransport:
    def __init__(self, payload: Any):
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append({"method": method, "url": url})
        return _FakeResponse(self.payload if len(self.calls) == 1 else [])


def _setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")


def _promote(monkeypatch: pytest.MonkeyPatch, endpoint_id: str) -> None:
    """Temporarily flip a financial adapter to live_verified=True (test-only; the
    on-disk registry is untouched) so the dispatch chain can run under fake transport."""
    base = ep_registry.get(endpoint_id)
    assert base is not None
    promoted = replace(base, live_verified=True)
    monkeypatch.setitem(ep_registry._BY_ID, endpoint_id, promoted)
    if base.legacy_endpoint_alias:
        monkeypatch.setitem(ep_registry._BY_LEGACY, base.legacy_endpoint_alias, promoted)


_PRIME_PAYLOAD = [
    {
        "id": 5001,
        "number": "PC-1",
        "status": "Approved",
        "executed": False,
        "grand_total": "1000000.00",
        "original_contract_amount": "950000.00",
        "retainage_percent": "10.00",
        "currency_configuration": {"currency_iso_code": "USD"},
    }
]


def _sync(db: Path, transport: _FakeTransport) -> Dict[str, Any]:
    return run_live_sync(
        project_key="tropical",
        endpoint="prime-contracts",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=3,
        max_items=100,
        db_path=db,
        transport=transport,
    )


def test_budget_change_history_synthetic_record_id() -> None:
    # budget-change-history records carry no `id`; the orchestrator must derive a
    # deterministic synthetic id (else every record is skipped with missing_record_id).
    from hb_assistant.procore.live_sync import _record_id_of

    adapter = ep_registry.get("budget-change-history")
    rec = {
        "budget_code": "01-100",
        "column": "Revised",
        "created_at": "2026-05-20",
        "old_value": "100.00",
        "new_value": "150.00",
    }
    rid1 = _record_id_of(adapter, rec)
    rid2 = _record_id_of(adapter, dict(rec))
    assert rid1 and rid1.startswith("h:") and rid1 == rid2  # deterministic
    # a different change yields a different id
    assert _record_id_of(adapter, {**rec, "new_value": "200.00"}) != rid1
    # a record that DOES carry an id uses it verbatim
    assert _record_id_of(adapter, {**rec, "id": 77}) == "77"


def test_prime_contract_full_dispatch_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    _promote(monkeypatch, "prime-contracts")
    db = _db()

    receipt = _sync(db, _FakeTransport(_PRIME_PAYLOAD))

    assert receipt["state"] == "success" and receipt["status"] == "success"
    assert receipt["parent_upserted_count"] == 1 and receipt["normalized_count"] == 1
    assert receipt["projection_error_count"] == 0
    assert receipt["raw_body_persisted"] is False and receipt["secrets_redacted"] is True
    # (a) latest-state row
    live = [r for r in _rows(db, "procore_live_records") if r["endpoint_id"] == "prime-contracts"]
    assert len(live) == 1
    # (b) history recorded (snapshot/timeline)
    assert _rows(db, "procore_live_record_snapshots")
    # (c) financial projection ran
    contracts = _rows(db, "procore_financial_contracts")
    assert len(contracts) == 1 and contracts[0]["grand_total"] == "1000000.00"
    facts = {f["amount_name"] for f in _rows(db, "procore_financial_amount_facts")}
    assert {"grand_total", "original_contract_sum", "retainage_percent"} <= facts


def test_prime_contract_resync_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    _promote(monkeypatch, "prime-contracts")
    db = _db()

    _sync(db, _FakeTransport(_PRIME_PAYLOAD))
    facts_after_first = len(_rows(db, "procore_financial_amount_facts"))
    receipt2 = _sync(db, _FakeTransport(_PRIME_PAYLOAD))

    assert receipt2["state"] == "success"
    assert len(_rows(db, "procore_financial_contracts")) == 1  # no duplicate
    assert len(_rows(db, "procore_live_records")) == 1
    assert len(_rows(db, "procore_financial_amount_facts")) == facts_after_first  # stable


def test_projection_failure_captured_without_breaking_latest_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    _promote(monkeypatch, "prime-contracts")
    db = _db()

    def _boom(*args: object, **kwargs: object) -> Dict[str, Any]:
        raise RuntimeError("synthetic projection failure")

    monkeypatch.setattr("hb_assistant.procore.live_sync.project_owner_contract_family", _boom)

    receipt = _sync(db, _FakeTransport(_PRIME_PAYLOAD))

    # latest-state sync still completes (state reflects the captured projection
    # error as partial_success) — the upsert + history are NOT rolled back.
    assert receipt["state"] in ("success", "partial_success")
    assert receipt["no_live_call_performed"] is False
    assert receipt["sqlite_upserted_count"] >= 1
    assert len(_rows(db, "procore_live_records")) == 1
    assert _rows(db, "procore_live_record_snapshots")  # history still recorded
    # projection failure captured (count + redacted detail), financial table empty
    assert receipt["projection_error_count"] >= 1
    assert any("owner_projection_error" in err for err in receipt["redacted_errors"])
    assert _rows(db, "procore_financial_contracts") == []
