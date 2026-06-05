"""Phase 06B Prompt 03 — N+1 rate-limit / cadence hardening (offline, fake transport).

Proves the bounded child-request cap for N+1 endpoints: bounded fan-out, cap-reached
receipt fields, idempotency + parent/child linkage under a cap, partial-success on a
per-parent child error, and no raw error leakage. No live Procore.
"""

from __future__ import annotations

import json
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

_ENDPOINT = "commitment-line-items"
_RAW_ERROR = "synthetic child transport failure"


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _child_rows(db: Path) -> List[sqlite3.Row]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM procore_live_records WHERE endpoint_id=?", (_ENDPOINT,)
        ).fetchall()
    finally:
        conn.close()


def _promote(monkeypatch: pytest.MonkeyPatch, endpoint_id: str) -> None:
    base = ep_registry.get(endpoint_id)
    assert base is not None
    monkeypatch.setitem(ep_registry._BY_ID, endpoint_id, replace(base, live_verified=True))


def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    _promote(monkeypatch, _ENDPOINT)


class _FakeResponse:
    def __init__(
        self,
        body: Any,
        *,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._body = body
        self.status_code = status_code
        self.headers: Dict[str, str] = dict(headers or {})
        self.text = ""

    def json(self) -> Any:
        return self._body


class _ManyParentsTransport:
    """Parent list of N commitment_contracts; one line item per parent. Parents whose id
    is in ``error_ids`` raise on their child GET (per-parent error path)."""

    def __init__(self, parent_ids: List[int], error_ids: tuple[int, ...] = ()) -> None:
        self.parent_ids = parent_ids
        self.error_ids = set(error_ids)
        self.calls: List[str] = []
        self.child_calls: List[str] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append(url)
        page = int((params or {}).get("page", 1))
        if url.rstrip("/").endswith("/commitment_contracts"):  # parent list
            body = [{"id": p} for p in self.parent_ids] if page == 1 else []
            return _FakeResponse({"data": body})
        if "/commitment_contracts/" in url and url.endswith("/line_items"):  # child
            pid = url.split("/commitment_contracts/")[1].split("/")[0]
            self.child_calls.append(pid)
            if int(pid) in self.error_ids:
                raise RuntimeError(_RAW_ERROR)
            if page != 1:
                return _FakeResponse({"data": []})
            return _FakeResponse(
                {
                    "data": [
                        {
                            "id": int(pid) * 10 + 1,
                            "amount": "100.00",
                            "wbs_code": {"id": 3, "flat_code": "01-100"},
                        }
                    ]
                }
            )
        return _FakeResponse({"data": []})


class _RateLimitOnChildTransport(_ManyParentsTransport):
    """Return a Procore-style 429 on one child GET; later parents must not be called."""

    def __init__(self, parent_ids: List[int], rate_limited_parent_id: int) -> None:
        super().__init__(parent_ids)
        self.rate_limited_parent_id = rate_limited_parent_id

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        if "/commitment_contracts/" in url and url.endswith("/line_items"):
            pid = url.split("/commitment_contracts/")[1].split("/")[0]
            self.calls.append(url)
            self.child_calls.append(pid)
            if int(pid) == self.rate_limited_parent_id:
                return _FakeResponse(
                    {"error": "rate_limited"},
                    status_code=429,
                    headers={"Retry-After": "2"},
                )
            return _FakeResponse({"data": [{"id": int(pid) * 10 + 1, "amount": "100.00"}]})
        return super().__call__(method, url, headers, params)


class _RateLimitThenSuccessChildTransport(_ManyParentsTransport):
    """One child GET gets a 429 once, then succeeds when retried."""

    def __init__(self, parent_ids: List[int], rate_limited_parent_id: int) -> None:
        super().__init__(parent_ids)
        self.rate_limited_parent_id = rate_limited_parent_id
        self._rate_limit_returned = False

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        if "/commitment_contracts/" in url and url.endswith("/line_items"):
            pid = url.split("/commitment_contracts/")[1].split("/")[0]
            self.calls.append(url)
            self.child_calls.append(pid)
            if int(pid) == self.rate_limited_parent_id and not self._rate_limit_returned:
                self._rate_limit_returned = True
                return _FakeResponse(
                    {"error": "rate_limited"},
                    status_code=429,
                    headers={"Retry-After": "2"},
                )
            return _FakeResponse({"data": [{"id": int(pid) * 10 + 1, "amount": "100.00"}]})
        return super().__call__(method, url, headers, params)


class _EmptyChildTransport:
    """Generic N+1 transport: parent list has many rows, every child list is empty."""

    def __init__(self, endpoint_id: str, parent_ids: List[int]) -> None:
        adapter = ep_registry.get(endpoint_id)
        assert adapter is not None and adapter.parent_path_template is not None
        self.endpoint_id = endpoint_id
        self.parent_path = adapter.parent_path_template.replace("{project_id}", "2525840").replace(
            "{company_id}", "5280"
        )
        self.parent_ids = parent_ids
        self.calls: List[str] = []
        self.child_calls: List[str] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append(url)
        if url.endswith(self.parent_path):
            rows: List[Dict[str, Any]] = []
            for parent_id in self.parent_ids:
                row: Dict[str, Any] = {"id": parent_id}
                if self.endpoint_id in {"rfq-responses", "rfq-quotes"}:
                    row["commitment_contract_id"] = "701973"
                rows.append(row)
            return _FakeResponse({"data": rows})
        self.child_calls.append(url)
        return _FakeResponse({"data": []})


class _CommitmentComplianceTransport:
    def __init__(self) -> None:
        self.calls: List[str] = []
        self.child_calls: List[str] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append(url)
        page = int((params or {}).get("page", 1))
        if url.rstrip("/").endswith("/commitment_contracts"):
            if page != 1:
                return _FakeResponse({"data": []})
            return _FakeResponse(
                {
                    "data": [
                        {"id": 101, "type": "WorkOrderContract"},
                        {"id": 202, "type": "PurchaseOrderContract"},
                        {"id": 303, "type": "WorkOrderContract"},
                    ]
                }
            )
        if "/work_order_contracts/" in url and url.endswith("/compliance"):
            contract_id = url.split("/work_order_contracts/")[1].split("/")[0]
            self.child_calls.append(contract_id)
            return _FakeResponse(
                {
                    "contract_id": contract_id,
                    "compliance_status": "compliant",
                    "insurance_status": "compliant",
                }
            )
        return _FakeResponse({"data": []})


class _RateLimitThenSuccessParentTransport(_ManyParentsTransport):
    """The parent list gets one 429 without Retry-After, then succeeds."""

    def __init__(self, parent_ids: List[int]) -> None:
        super().__init__(parent_ids)
        self._parent_rate_limit_returned = False

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        if url.rstrip("/").endswith("/commitment_contracts"):
            self.calls.append(url)
            if not self._parent_rate_limit_returned:
                self._parent_rate_limit_returned = True
                return _FakeResponse({"error": "rate_limited"}, status_code=429)
            page = int((params or {}).get("page", 1))
            body = [{"id": p} for p in self.parent_ids] if page == 1 else []
            return _FakeResponse({"data": body})
        return super().__call__(method, url, headers, params)


def _run(db: Path, transport: Any, *, max_child_requests: int) -> Dict[str, Any]:
    return run_live_sync(
        project_key="tropical",
        endpoint=_ENDPOINT,
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=50,
        max_child_requests=max_child_requests,
        db_path=db,
        transport=transport,
    )


def test_commitment_compliance_skips_purchase_order_contract_parents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup(monkeypatch)
    _promote(monkeypatch, "commitment-compliance")
    db = _db()
    transport = _CommitmentComplianceTransport()

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="commitment-compliance",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        max_child_requests=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["status"] == "success"
    assert transport.child_calls == ["101", "303"]
    assert receipt["n1_fanout"]["parent_count"] == 3
    assert receipt["n1_fanout"]["child_request_count"] == 2
    assert receipt["n1_fanout"]["child_skipped_count"] == 1
    assert receipt["n1_fanout"]["child_incompatible_parent_skipped_count"] == 1
    assert receipt["sqlite_upserted_count"] == 2


# --- Bounded fan-out: cap < parents ----------------------------------------------------
def test_bounded_fanout_caps_child_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(monkeypatch)
    db = _db()
    transport = _ManyParentsTransport(parent_ids=[501, 502, 503, 504, 505])
    receipt = _run(db, transport, max_child_requests=2)

    # exactly `cap` child GETs were issued; the other 3 parents were skipped.
    assert len(transport.child_calls) == 2
    fan = receipt["n1_fanout"]
    assert fan == {
        "is_n1": True,
        "parent_count": 5,
        "child_request_count": 2,
        "child_skipped_count": 3,
        "child_incompatible_parent_skipped_count": 0,
        "child_error_count": 0,
        "cap": 2,
        "cap_reached": True,
        "rate_limit_stopped": False,
        "rate_limit_parent_id": None,
        "child_request_delay_seconds": 0.0,
        "rate_limit_wait_count": 0,
        "rate_limit_sleep_seconds_total": 0.0,
    }
    assert "n1_child_cap_reached" in receipt["reason_codes"]
    # only the capped parents' children landed (501, 502).
    rows = _child_rows(db)
    assert len(rows) == 2
    assert {r["parent_procore_id"] for r in rows} == {"501", "502"}


# --- Cap does not break idempotency or parent/child linkage (stop condition) -----------
def test_capped_run_is_idempotent_and_preserves_linkage(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(monkeypatch)
    db = _db()
    first = _run(db, _ManyParentsTransport([501, 502, 503, 504, 505]), max_child_requests=2)
    rows_first = _child_rows(db)
    # second identical run upserts the same records -> no duplicates, linkage intact.
    second = _run(db, _ManyParentsTransport([501, 502, 503, 504, 505]), max_child_requests=2)
    rows_second = _child_rows(db)

    assert first["n1_fanout"]["cap_reached"] is True
    assert second["n1_fanout"]["cap_reached"] is True
    assert len(rows_first) == len(rows_second) == 2
    assert {r["procore_record_id"] for r in rows_first} == {
        r["procore_record_id"] for r in rows_second
    }
    assert all(r["parent_procore_id"] in {"501", "502"} for r in rows_second)


# --- Uncapped when parents are below the cap (behavior preserved) -----------------------
def test_no_cap_when_parents_below_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(monkeypatch)
    db = _db()
    receipt = _run(db, _ManyParentsTransport([501, 502, 503]), max_child_requests=50)
    fan = receipt["n1_fanout"]
    assert fan["parent_count"] == 3 and fan["child_request_count"] == 3
    assert fan["child_skipped_count"] == 0 and fan["cap_reached"] is False
    assert "n1_child_cap_reached" not in receipt["reason_codes"]
    assert len(_child_rows(db)) == 3


# --- Partial success: per-parent child error is captured, run continues ----------------
def test_partial_success_continues_on_child_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(monkeypatch)
    db = _db()
    receipt = _run(
        db, _ManyParentsTransport([501, 502, 503], error_ids=(503,)), max_child_requests=50
    )
    fan = receipt["n1_fanout"]
    assert fan["child_request_count"] == 3
    assert fan["child_error_count"] == 1
    assert fan["cap_reached"] is False
    assert receipt["state"] in ("success", "partial_success")
    assert any("detail_transport_error" in e for e in receipt["redacted_errors"])
    # the two healthy parents' children still persisted with linkage.
    rows = _child_rows(db)
    assert {r["parent_procore_id"] for r in rows} == {"501", "502"}


# --- Rate limit: stop this endpoint's fanout immediately ------------------------------
def test_rate_limited_child_stops_remaining_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(monkeypatch)
    db = _db()
    transport = _RateLimitOnChildTransport([501, 502, 503, 504], rate_limited_parent_id=503)
    receipt = _run(db, transport, max_child_requests=50)

    fan = receipt["n1_fanout"]
    assert fan["child_request_count"] == 3
    assert fan["child_error_count"] == 1
    assert fan["child_skipped_count"] == 1
    assert fan["rate_limit_stopped"] is True
    assert fan["rate_limit_parent_id"] == "503"
    assert receipt["last_retry_after"] == 2
    assert "n1_child_rate_limited" in receipt["reason_codes"]
    assert transport.child_calls == ["501", "502", "503"]
    rows = _child_rows(db)
    assert {r["parent_procore_id"] for r in rows} == {"501", "502"}


def test_wait_on_rate_limit_retries_same_child_then_resumes_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup(monkeypatch)
    db = _db()
    sleeps: List[float] = []
    transport = _RateLimitThenSuccessChildTransport(
        [501, 502, 503, 504], rate_limited_parent_id=503
    )

    receipt = run_live_sync(
        project_key="tropical",
        endpoint=_ENDPOINT,
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=50,
        max_child_requests=50,
        wait_on_rate_limit=True,
        rate_limit_fallback_sleep_seconds=3660.0,
        max_rate_limit_wait_cycles=1,
        sleep_fn=sleeps.append,
        db_path=db,
        transport=transport,
    )

    fan = receipt["n1_fanout"]
    assert receipt["state"] == "success"
    assert receipt["rate_limit_wait_count"] == 1
    assert receipt["rate_limit_sleep_seconds_total"] == 2.0
    assert receipt["last_retry_after"] == 2
    assert sleeps == [2.0]
    assert fan["child_request_count"] == 5
    assert fan["child_error_count"] == 0
    assert fan["rate_limit_stopped"] is False
    assert "n1_child_rate_limit_waited" in receipt["reason_codes"]
    assert transport.child_calls == ["501", "502", "503", "503", "504"]
    rows = _child_rows(db)
    assert {r["parent_procore_id"] for r in rows} == {"501", "502", "503", "504"}


def test_wait_on_rate_limit_uses_fallback_for_parent_list_without_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup(monkeypatch)
    db = _db()
    sleeps: List[float] = []
    transport = _RateLimitThenSuccessParentTransport([501])

    receipt = run_live_sync(
        project_key="tropical",
        endpoint=_ENDPOINT,
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=50,
        max_child_requests=50,
        wait_on_rate_limit=True,
        rate_limit_fallback_sleep_seconds=3660.0,
        max_rate_limit_wait_cycles=1,
        sleep_fn=sleeps.append,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["rate_limit_wait_count"] == 1
    assert receipt["rate_limit_sleep_seconds_total"] == 3660.0
    assert sleeps == [3660.0]
    assert "parent_list_rate_limit_waited" in receipt["reason_codes"]
    assert len([url for url in transport.calls if url.endswith("/commitment_contracts")]) == 2
    assert receipt["n1_fanout"]["child_request_count"] == 1


@pytest.mark.parametrize(
    "endpoint_id",
    [
        "subcontractor-invoice-contract-detail-items",
        "subcontractor-invoice-change-order-items",
        "rfq-responses",
        "rfq-quotes",
        "change-event-comments",
        "budget-detail-columns",
        "budget-detail-rows",
    ],
)
def test_unreached_n1_endpoints_share_bounded_fanout(
    monkeypatch: pytest.MonkeyPatch, endpoint_id: str
) -> None:
    _setup(monkeypatch)
    _promote(monkeypatch, endpoint_id)
    db = _db()
    transport = _EmptyChildTransport(endpoint_id, [501, 502, 503, 504])

    receipt = run_live_sync(
        project_key="tropical",
        endpoint=endpoint_id,
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=50,
        max_child_requests=2,
        db_path=db,
        transport=transport,
    )

    fan = receipt["n1_fanout"]
    assert fan["parent_count"] == 4
    assert fan["child_request_count"] == 2
    assert fan["child_skipped_count"] == 2
    assert fan["cap_reached"] is True
    assert fan["rate_limit_stopped"] is False
    assert "n1_child_cap_reached" in receipt["reason_codes"]
    assert len(transport.child_calls) == 2


# --- No raw error leakage --------------------------------------------------------------
def test_no_raw_child_error_leakage(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(monkeypatch)
    db = _db()
    receipt = _run(
        db, _ManyParentsTransport([501, 502, 503], error_ids=(503,)), max_child_requests=50
    )
    # the raw exception text never appears anywhere in the receipt.
    assert _RAW_ERROR not in json.dumps(receipt, default=str)
    # each redacted error entry exposes only the classified keys (error code/status + the
    # parent-id pointer token); no raw body / message.
    token = ep_registry.get(_ENDPOINT).parent_record_id_field or "id"
    allowed = {"detail_transport_error", "status", token}
    for err in receipt["redacted_errors"]:
        assert "detail_transport_error" in err
        assert set(err.keys()) <= allowed
        assert _RAW_ERROR not in json.dumps(err, default=str)
