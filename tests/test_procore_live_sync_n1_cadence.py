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
    def __init__(self, body: Any) -> None:
        self._body = body
        self.status_code = 200
        self.headers: Dict[str, str] = {}
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
                {"data": [{"id": int(pid) * 10 + 1, "amount": "100.00",
                           "wbs_code": {"id": 3, "flat_code": "01-100"}}]}
            )
        return _FakeResponse({"data": []})


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
        "child_error_count": 0,
        "cap": 2,
        "cap_reached": True,
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
    assert {r["procore_record_id"] for r in rows_first} == {r["procore_record_id"] for r in rows_second}
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
    receipt = _run(db, _ManyParentsTransport([501, 502, 503], error_ids=(503,)), max_child_requests=50)
    fan = receipt["n1_fanout"]
    assert fan["child_request_count"] == 3
    assert fan["child_error_count"] == 1
    assert fan["cap_reached"] is False
    assert receipt["state"] in ("success", "partial_success")
    assert any("detail_transport_error" in e for e in receipt["redacted_errors"])
    # the two healthy parents' children still persisted with linkage.
    rows = _child_rows(db)
    assert {r["parent_procore_id"] for r in rows} == {"501", "502"}


# --- No raw error leakage --------------------------------------------------------------
def test_no_raw_child_error_leakage(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(monkeypatch)
    db = _db()
    receipt = _run(db, _ManyParentsTransport([501, 502, 503], error_ids=(503,)), max_child_requests=50)
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
