"""Phase 04A verified endpoint live chain end-to-end (fake transport)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_repositories import count_procore_live_records

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


class _FakeResponse:
    def __init__(self, body: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None):
        self._json_body = body
        self.status_code = status_code
        self.headers = headers or {}
        self.text = ""

    def json(self) -> Any:
        return self._json_body


class _FakeTransport:
    """Records every call and returns a fixed JSON body."""

    def __init__(self, payload: List[Dict[str, Any]]):
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]],
    ) -> _FakeResponse:
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers), "params": dict(params or {})}
        )
        # Return all items on the first call, empty on subsequent (pagination halts).
        if len(self.calls) == 1:
            return _FakeResponse(self.payload)
        return _FakeResponse([])


_RFI_PAYLOAD = [
    {
        "id": 101,
        "number": "RFI-001",
        "subject": "Door schedule clarification",
        "status": "open",
        "updated_at": "2026-01-01T00:00:00Z",
        "assignee_id": 42,
    },
    {
        "id": 102,
        "number": "RFI-002",
        "subject": "Claim impact - delay review",  # triggers review_required
        "status": "open",
        "updated_at": "2026-01-02T00:00:00Z",
        "assignee_id": 43,
    },
]


def _setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")


def test_verified_rfis_endpoint_runs_full_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=3,
        max_items=100,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["status"] == "success"
    assert receipt["retrieved_count"] == 2
    assert receipt["normalized_count"] == 2
    assert receipt["sqlite_upserted_count"] == 2
    assert receipt["sqlite_total_count_after"] == 2
    assert receipt["raw_body_persisted"] is False
    assert receipt["secrets_redacted"] is True
    assert receipt["http_method"] == "GET"
    assert receipt["endpoint_id"] == "rfis"
    assert receipt["legacy_endpoint_alias"] == "list-rfis"
    assert receipt["procore_project_id"] == "2525840"


def test_transport_receives_bearer_access_token_not_client_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "MUST_NEVER_APPEAR_IN_AUTH_HEADER")
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    assert transport.calls, "transport must be invoked"
    auth = transport.calls[0]["headers"]["Authorization"]
    assert auth == "Bearer synthetic-bearer-token"
    assert "MUST_NEVER_APPEAR_IN_AUTH_HEADER" not in auth
    assert transport.calls[0]["method"] == "GET"


def test_only_get_method_observed_by_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    for call in transport.calls:
        assert call["method"] == "GET"


def test_verified_chain_is_idempotent_across_re_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()

    def _go() -> Dict[str, Any]:
        return run_live_sync(
            project_key="tropical",
            endpoint="rfis",
            apply=True,
            sqlite_only=True,
            confirm_live_get=True,
            db_path=db,
            transport=_FakeTransport(_RFI_PAYLOAD),
        )

    first = _go()
    second = _go()
    assert first["sqlite_upserted_count"] == 2
    assert second["sqlite_upserted_count"] == 2  # upsert, not duplicate insert
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfis", db_path=db
    ) == 2


def test_smoke_mode_does_not_write_to_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=False,
        sqlite_only=False,
        confirm_live_get=True,
        mode_hint="live_smoke",
        db_path=db,
        transport=transport,
    )
    assert receipt["state"] == "success"
    assert receipt["mode"] == "live_smoke"
    assert receipt["retrieved_count"] == 2
    assert receipt["normalized_count"] == 2
    assert receipt["sqlite_upserted_count"] == 0
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfis", db_path=db
    ) == 0


def test_raw_response_body_never_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_json_redacted, raw_body_persisted FROM procore_live_records"
        ).fetchall()
    finally:
        conn.close()
    assert rows, "expected at least one persisted row"
    for canonical_json, raw_body_persisted in rows:
        # Body never persisted (constraint enforces 0)
        assert raw_body_persisted == 0
        # Canonical JSON must not include "Bearer" or the synthetic token value
        assert "Bearer" not in canonical_json
        assert "synthetic-bearer-token" not in canonical_json


def test_review_required_flag_set_on_sensitive_rfi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT review_required, sensitive_reason FROM procore_live_records "
            "WHERE procore_record_id = '102' AND endpoint_id = 'rfis'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == 1
    assert row[1] is not None and "claim" in row[1].lower()


# ----------------------------------------------------------------------------
# Phase 04A Prompt 04: RFI + replies (N+1 child fetch)
# ----------------------------------------------------------------------------


class _PathAwareFakeTransport:
    """Returns a different JSON body depending on which path was requested.

    `path_to_payload` is a mapping from URL substring to a list-of-dicts body.
    Any URL whose substring matches none returns an empty list.
    `error_paths` is a mapping from URL substring to (status_code, body).
    """

    def __init__(
        self,
        path_to_payload: Dict[str, List[Dict[str, Any]]],
        error_paths: Optional[Dict[str, int]] = None,
    ) -> None:
        self.path_to_payload = path_to_payload
        self.error_paths = error_paths or {}
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]],
    ) -> _FakeResponse:
        self.calls.append({"method": method, "url": url})
        for needle, code in self.error_paths.items():
            if needle in url:
                return _FakeResponse([], status_code=code)
        for needle, body in self.path_to_payload.items():
            if needle in url:
                return _FakeResponse(body)
        return _FakeResponse([])


def _reply(reply_id: int) -> Dict[str, Any]:
    return {
        "id": reply_id,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "author_id": 99,
        "body": "Reply text that must never appear in canonical storage.",
    }


def _rfi_with_replies(rfi_id: int, subject: str, *, replies: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "id": rfi_id,
        "number": f"RFI-{rfi_id}",
        "subject": subject,
        "status": "open",
        "updated_at": "2026-01-01T00:00:00Z",
        "assignee_id": 42,
        "replies": replies,
    }


def test_rfis_apply_persists_parents_and_replies_inline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    payload = [
        _rfi_with_replies(101, "Door schedule", replies=[_reply(9001), _reply(9002), _reply(9003)]),
        _rfi_with_replies(102, "Claim impact - delay review", replies=[_reply(9101), _reply(9102)]),
    ]
    transport = _FakeTransport(payload)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["parent_upserted_count"] == 2
    assert receipt["child_upserted_count"] == 5
    assert receipt["child_endpoint_id"] == "rfi-responses"
    assert receipt["sqlite_upserted_count"] == 7
    assert receipt["child_errors_count"] == 0
    # Only ONE HTTP call: the parent list. Children come inline (no N+1).
    assert len(transport.calls) == 1
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfis", db_path=db
    ) == 2
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfi-responses", db_path=db
    ) == 5


def test_rfis_apply_is_idempotent_for_parents_and_replies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    payload = [
        _rfi_with_replies(101, "Door schedule", replies=[_reply(9001), _reply(9002)]),
        _rfi_with_replies(102, "Claim impact - delay review", replies=[_reply(9101)]),
    ]

    def _go() -> Dict[str, Any]:
        return run_live_sync(
            project_key="tropical",
            endpoint="rfis",
            apply=True,
            sqlite_only=True,
            confirm_live_get=True,
            max_pages=1,
            max_items=10,
            db_path=db,
            transport=_FakeTransport(payload),
        )

    first = _go()
    second = _go()
    assert first["sqlite_upserted_count"] == 5
    assert second["sqlite_upserted_count"] == 5
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfis", db_path=db
    ) == 2
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfi-responses", db_path=db
    ) == 3


def test_rfis_apply_tolerates_missing_replies_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parent RFI without an inline ``replies`` field upserts cleanly with
    zero children. The orchestrator does not issue any additional GET."""
    _setup_env(monkeypatch)
    db = _db()
    payload = [
        _rfi_with_replies(101, "Door schedule", replies=[_reply(9001), _reply(9002)]),
        {
            "id": 102,
            "number": "RFI-102",
            "subject": "No replies field",
            "status": "open",
            "updated_at": "2026-01-01T00:00:00Z",
            "assignee_id": 43,
            # no "replies" key
        },
    ]
    transport = _FakeTransport(payload)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["parent_upserted_count"] == 2
    assert receipt["child_upserted_count"] == 2  # only RFI 101's replies
    assert receipt["child_errors_count"] == 0
    # Still only one HTTP call.
    assert len(transport.calls) == 1


def test_rfi_reply_canonical_json_carries_no_body_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    secret_body_marker = "MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE"
    reply_with_marker = {
        "id": 7777,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "author_id": 50,
        "body": secret_body_marker,
    }
    payload = [
        _rfi_with_replies(101, "Door schedule", replies=[reply_with_marker]),
        _rfi_with_replies(102, "Other", replies=[]),
    ]
    transport = _FakeTransport(payload)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_json_redacted, review_required, parent_procore_id, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id = 'rfi-responses'"
        ).fetchall()
    finally:
        conn.close()
    assert rows, "expected at least one reply row"
    for canonical_json, review_required, parent_procore_id, raw_body_persisted in rows:
        assert secret_body_marker not in canonical_json
        assert review_required == 1
        assert parent_procore_id in {"101", "102"}
        assert raw_body_persisted == 0


# ----------------------------------------------------------------------------
# Phase 04A Prompt 05: submittals + responses (N+1 child fetch)
# ----------------------------------------------------------------------------


_SUBMITTAL_PAYLOAD = [
    {
        "id": 201,
        "number": "SUB-001",
        "title": "Door hardware schedule",
        "status": "open",
        "updated_at": "2026-02-01T00:00:00Z",
        "assignee_id": 51,
    },
    {
        "id": 202,
        "number": "SUB-002",
        "title": "Claim impact - revise & resubmit",  # triggers review_required
        "status": "open",
        "updated_at": "2026-02-02T00:00:00Z",
        "assignee_id": 52,
    },
]


def _submittal_response(response_id: int) -> Dict[str, Any]:
    return {
        "id": response_id,
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
        "author_id": 88,
        "response_status": "approved",
        "comment": "Response text that must never appear in canonical storage.",
    }


def _submittal_with_responses(
    submittal_id: int, title: str, *, responses: List[Dict[str, Any]]
) -> Dict[str, Any]:
    return {
        "id": submittal_id,
        "number": f"SUB-{submittal_id}",
        "title": title,
        "status": "open",
        "updated_at": "2026-02-01T00:00:00Z",
        "assignee_id": 51,
        "responses": responses,
    }


def test_submittals_apply_persists_parents_and_responses_inline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    payload = [
        _submittal_with_responses(
            201,
            "Door hardware",
            responses=[
                _submittal_response(8001),
                _submittal_response(8002),
                _submittal_response(8003),
            ],
        ),
        _submittal_with_responses(
            202,
            "Claim impact - revise & resubmit",
            responses=[_submittal_response(8101), _submittal_response(8102)],
        ),
    ]
    transport = _FakeTransport(payload)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="submittals",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["parent_upserted_count"] == 2
    assert receipt["child_upserted_count"] == 5
    assert receipt["child_endpoint_id"] == "submittal-responses"
    assert receipt["sqlite_upserted_count"] == 7
    assert receipt["child_errors_count"] == 0
    assert len(transport.calls) == 1
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="submittals", db_path=db
    ) == 2
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="submittal-responses", db_path=db
    ) == 5


def test_submittals_apply_is_idempotent_for_parents_and_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    payload = [
        _submittal_with_responses(
            201,
            "Door hardware",
            responses=[_submittal_response(8001), _submittal_response(8002)],
        ),
        _submittal_with_responses(
            202, "Claim impact", responses=[_submittal_response(8101)]
        ),
    ]

    def _go() -> Dict[str, Any]:
        return run_live_sync(
            project_key="tropical",
            endpoint="submittals",
            apply=True,
            sqlite_only=True,
            confirm_live_get=True,
            max_pages=1,
            max_items=10,
            db_path=db,
            transport=_FakeTransport(payload),
        )

    first = _go()
    second = _go()
    assert first["sqlite_upserted_count"] == 5
    assert second["sqlite_upserted_count"] == 5
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="submittals", db_path=db
    ) == 2
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="submittal-responses", db_path=db
    ) == 3


def test_submittals_apply_tolerates_missing_responses_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parent submittal without an inline ``responses`` field upserts cleanly
    with zero children. No additional HTTP request is issued."""
    _setup_env(monkeypatch)
    db = _db()
    payload = [
        _submittal_with_responses(
            201,
            "Door hardware",
            responses=[_submittal_response(8001), _submittal_response(8002)],
        ),
        {
            "id": 202,
            "number": "SUB-202",
            "title": "No responses field",
            "status": "open",
            "updated_at": "2026-02-02T00:00:00Z",
            "assignee_id": 52,
        },
    ]
    transport = _FakeTransport(payload)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="submittals",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["parent_upserted_count"] == 2
    assert receipt["child_upserted_count"] == 2
    assert receipt["child_errors_count"] == 0
    assert len(transport.calls) == 1


def test_submittal_response_canonical_json_carries_no_body_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    secret_body_marker = "MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE"
    response_with_marker = {
        "id": 7777,
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
        "author_id": 60,
        "response_status": "approved",
        "comment": secret_body_marker,
    }
    payload = [
        _submittal_with_responses(
            201, "Door hardware", responses=[response_with_marker]
        ),
        _submittal_with_responses(202, "Other", responses=[]),
    ]
    transport = _FakeTransport(payload)
    run_live_sync(
        project_key="tropical",
        endpoint="submittals",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_json_redacted, review_required, parent_procore_id, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id = 'submittal-responses'"
        ).fetchall()
    finally:
        conn.close()
    assert rows, "expected at least one response row"
    for canonical_json, review_required, parent_procore_id, raw_body_persisted in rows:
        assert secret_body_marker not in canonical_json
        assert review_required == 1
        assert parent_procore_id in {"201", "202"}
        assert raw_body_persisted == 0


# ----------------------------------------------------------------------------
# Phase 04A Prompt 06: observations (parent-only, high-sensitivity routing)
# ----------------------------------------------------------------------------


_OBSERVATION_PAYLOAD = [
    # 1) Safety fragment hit -> review_required=True, safety_route=True.
    {
        "id": 301,
        "number": "OBS-001",
        "title": "Near miss at south entry",
        "status": "near miss",
        "type": {"category": "Safety"},
        "assignee_id": 71,
        "updated_at": "2026-03-01T00:00:00Z",
    },
    # 2) Bland subject, status, type, and an assignee -> default_low_risk.
    {
        "id": 302,
        "number": "OBS-002",
        "title": "Touch-up paint on stair handrail",
        "status": "open",
        "type": {"category": "Quality"},
        "assignee_id": 72,
        "updated_at": "2026-03-02T00:00:00Z",
    },
    # 3) Bland subject, no assignee -> review_required=True, reason=assignee_missing.
    {
        "id": 303,
        "number": "OBS-003",
        "title": "Routine punch-list item",
        "status": "open",
        "type": {"category": "Quality"},
        "updated_at": "2026-03-03T00:00:00Z",
    },
]


def test_observations_apply_persists_with_heuristic_review_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_OBSERVATION_PAYLOAD)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="observations",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["retrieved_count"] == 3
    assert receipt["normalized_count"] == 3
    assert receipt["sqlite_upserted_count"] == 3
    assert receipt["endpoint_id"] == "observations"
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="observations", db_path=db
    ) == 3

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT procore_record_id, review_required, sensitive_reason "
            "FROM procore_live_records WHERE endpoint_id='observations' "
            "ORDER BY procore_record_id"
        ).fetchall()
    finally:
        conn.close()

    by_id = {row[0]: (row[1], row[2]) for row in rows}
    # Safety fragment -> review_required=1
    assert by_id["301"][0] == 1
    assert by_id["301"][1] is not None
    # Default low-risk path -> review_required=0
    assert by_id["302"][0] == 0
    assert by_id["302"][1] == "default_low_risk"
    # Missing assignee fallback -> review_required=1, reason=assignee_missing
    assert by_id["303"][0] == 1
    assert by_id["303"][1] == "assignee_missing"


def test_observations_apply_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()

    def _go() -> Dict[str, Any]:
        return run_live_sync(
            project_key="tropical",
            endpoint="observations",
            apply=True,
            sqlite_only=True,
            confirm_live_get=True,
            max_pages=1,
            max_items=10,
            db_path=db,
            transport=_FakeTransport(_OBSERVATION_PAYLOAD),
        )

    first = _go()
    second = _go()
    assert first["sqlite_upserted_count"] == 3
    assert second["sqlite_upserted_count"] == 3
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="observations", db_path=db
    ) == 3


def test_observation_canonical_json_carries_no_description_body_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    secret_body_marker = "MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE"
    payload_with_marker = [
        {
            "id": 999,
            "number": "OBS-999",
            "title": "Sample with sensitive description",
            "status": "open",
            "type": {"category": "Safety"},
            "assignee_id": 81,
            "description": secret_body_marker,
            "updated_at": "2026-03-04T00:00:00Z",
        }
    ]
    transport = _FakeTransport(payload_with_marker)
    run_live_sync(
        project_key="tropical",
        endpoint="observations",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=5,
        db_path=db,
        transport=transport,
    )
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_json_redacted, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='observations'"
        ).fetchall()
    finally:
        conn.close()
    assert rows, "expected at least one observation row"
    for canonical_json, raw_body_persisted in rows:
        assert secret_body_marker not in canonical_json
        assert raw_body_persisted == 0


# ----------------------------------------------------------------------------
# Phase 04A Prompt 07: meetings + topics (N+1 child fetch)
# ----------------------------------------------------------------------------


@pytest.fixture
def _meetings_promoted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Temporarily promote the meetings adapter to live_verified=True so the
    N+1 dispatch path can be exercised under fake transport. In the registry
    meetings is held at live_verified=False because the v1.1 endpoint payload
    does not match the v1.0-shaped normalizer (see Prompt 07 probe matrix in
    docs/evidence/construction-intelligence-phase-04a/07-meeting-live-sync.md)."""
    from dataclasses import replace

    from hb_assistant.procore import endpoints as ep_registry

    base = ep_registry.get("meetings")
    assert base is not None
    promoted = replace(base, live_verified=True)
    monkeypatch.setitem(ep_registry._BY_ID, "meetings", promoted)
    if base.legacy_endpoint_alias:
        monkeypatch.setitem(
            ep_registry._BY_LEGACY, base.legacy_endpoint_alias, promoted
        )


_MEETING_PAYLOAD = [
    {
        "id": 401,
        "number": "MTG-001",
        "title": "Weekly OAC coordination",
        "status": "scheduled",
        "start_time": "2026-03-01T15:00:00Z",
        "end_time": "2026-03-01T16:00:00Z",
        "organizer_id": 91,
        "updated_at": "2026-02-28T00:00:00Z",
    },
    {
        "id": 402,
        "number": "MTG-002",
        "title": "Claim review meeting - delay impact",  # triggers review_required
        "status": "scheduled",
        "start_time": "2026-03-02T19:00:00Z",
        "end_time": "2026-03-02T20:00:00Z",
        "organizer_id": 92,
        "updated_at": "2026-03-01T00:00:00Z",
    },
]


def _meeting_topic(topic_id: int) -> Dict[str, Any]:
    return {
        "id": topic_id,
        "title": "Coordination update",
        "status": "open",
        "sequence_number": 1,
        "assignee_id": 99,
        "due_date": "2026-03-15",
        "description": "Topic discussion text that must never appear in canonical storage.",
        "created_at": "2026-03-01T00:00:00Z",
        "updated_at": "2026-03-01T00:00:00Z",
    }



def test_meetings_apply_flattens_v1_1_grouped_payload(
    monkeypatch: pytest.MonkeyPatch, _meetings_promoted: None,
) -> None:
    """Procore's v1.1 meetings endpoint returns grouped responses; the
    orchestrator must flatten before normalization. This test fakes the
    grouped wrapper and verifies one row lands per meeting (3), not per
    group (2)."""
    _setup_env(monkeypatch)
    db = _db()
    grouped_payload = [
        {
            "group_title": "Owner Architect Contractor",
            "meetings": [
                {
                    "id": 1001,
                    "title": "OAC weekly",
                    "starts_at": "2026-06-01T15:00:00Z",
                    "ends_at": "2026-06-01T16:00:00Z",
                    "created_by_id": 50,
                },
                {
                    "id": 1002,
                    "title": "OAC special session",
                    "starts_at": "2026-06-08T15:00:00Z",
                    "ends_at": "2026-06-08T16:30:00Z",
                    "created_by_id": 50,
                },
            ],
        },
        {
            "group_title": "Subcontractor coordination",
            "meetings": [
                {
                    "id": 2001,
                    "title": "Sub coord kickoff",
                    "starts_at": "2026-06-03T13:00:00Z",
                    "ends_at": "2026-06-03T14:00:00Z",
                    "created_by_id": 60,
                }
            ],
        },
    ]
    # Only the parent path returns the grouped payload; the per-meeting
    # topics paths return empty so no N+1 child rows confuse the assertion.
    transport = _PathAwareFakeTransport(
        {
            "/rest/v1.1/projects/2525840/meetings/1001/topics": [],
            "/rest/v1.1/projects/2525840/meetings/1002/topics": [],
            "/rest/v1.1/projects/2525840/meetings/2001/topics": [],
            "/rest/v1.0/projects/2525840/meetings/1001/topics": [],
            "/rest/v1.0/projects/2525840/meetings/1002/topics": [],
            "/rest/v1.0/projects/2525840/meetings/2001/topics": [],
            "/rest/v1.1/projects/2525840/meetings": grouped_payload,
        }
    )

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="meetings",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    # 3 meetings across 2 groups -> 3 parent rows persisted
    assert receipt["parent_upserted_count"] == 3
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="meetings", db_path=db
    ) == 3


# ----------------------------------------------------------------------------
# Phase 04A Prompt 08: selected daily-log sections (manpower / notes / delays)
# ----------------------------------------------------------------------------


def test_daily_log_delays_persists_with_review_routing_and_hash_only_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    secret_body_marker = "MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE"
    payload = [
        {
            "id": 501,
            "date": "2026-03-01",
            "delay_type": "weather",
            "impact_days": 1,
            "status": "open",
            "description": secret_body_marker,
            "cause": "Heavy rainfall delayed concrete pour",
            "updated_at": "2026-03-01T00:00:00Z",
        }
    ]
    transport = _FakeTransport(payload)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="daily-log-delays-review-routed",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=5,
        db_path=db,
        transport=transport,
    )
    assert receipt["state"] == "success"
    assert receipt["sqlite_upserted_count"] == 1
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT canonical_json_redacted, review_required, sensitive_reason, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='daily-log-delays-review-routed'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    canonical_json, review_required, sensitive_reason, raw_body_persisted = row
    assert review_required == 1
    assert sensitive_reason == "delays_section_safety_routed_critical"
    assert raw_body_persisted == 0
    assert secret_body_marker not in canonical_json
    assert "description_summary" in canonical_json  # hash present
    assert "hash_prefix" in canonical_json


def test_daily_log_notes_persists_with_review_required_and_hash_only_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    secret_body_marker = "MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE"
    payload = [
        {
            "id": 601,
            "date": "2026-03-02",
            "location": "Building A - L3",
            "author_id": 77,
            "note": secret_body_marker,
            "updated_at": "2026-03-02T00:00:00Z",
        }
    ]
    transport = _FakeTransport(payload)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="daily-log-notes",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=5,
        db_path=db,
        transport=transport,
    )
    assert receipt["state"] == "success"
    assert receipt["sqlite_upserted_count"] == 1
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT canonical_json_redacted, review_required, sensitive_reason, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='daily-log-notes'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    canonical_json, review_required, sensitive_reason, raw_body_persisted = row
    assert review_required == 1
    assert sensitive_reason == "notes_section_review_required_high_sensitivity"
    assert raw_body_persisted == 0
    assert secret_body_marker not in canonical_json
    assert "note_summary" in canonical_json
    assert "hash_prefix" in canonical_json


def test_daily_log_manpower_persists_with_review_required_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    payload = [
        {
            "id": 701,
            "date": "2026-03-03",
            "location": "Building B",
            "workers": 25,
            "hours": 200,
            "contractor_id": 9001,
            "updated_at": "2026-03-03T00:00:00Z",
        }
    ]
    transport = _FakeTransport(payload)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="daily-log-manpower",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=5,
        db_path=db,
        transport=transport,
    )
    assert receipt["state"] == "success"
    assert receipt["sqlite_upserted_count"] == 1
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT review_required, sensitive_reason, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='daily-log-manpower'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    review_required, sensitive_reason, raw_body_persisted = row
    assert review_required == 0
    assert sensitive_reason == "manpower_structured_low_risk"
    assert raw_body_persisted == 0


# ----------------------------------------------------------------------------
# Phase 04A final closeout: meeting-topics + daily-log-dcrs standalone
# ----------------------------------------------------------------------------


def test_meeting_topics_apply_persists_as_standalone_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """meeting-topics is a top-level v1.1 endpoint (/meeting_topics root noun),
    not a child extracted from a meetings parent payload. The orchestrator
    fetches it directly and normalizes via normalize_meeting_topic."""
    _setup_env(monkeypatch)
    db = _db()
    secret_body_marker = "MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE"
    payload = [
        {
            "id": 5001,
            "meeting_id": 8800,
            "title": "OAC coordination topic",
            "created_on": "2026-06-01T15:00:00Z",
            "minutes": secret_body_marker,
            "no_minutes": False,
            "marked": False,
            "meeting_position": 1,
        },
        {
            "id": 5002,
            "meeting_id": 8800,
            "title": "Schedule update",
            "created_on": "2026-06-01T15:30:00Z",
            "minutes": "Schedule details that should not leak.",
            "no_minutes": False,
            "marked": True,
            "meeting_position": 2,
        },
    ]
    transport = _FakeTransport(payload)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="meeting-topics",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["retrieved_count"] == 2
    assert receipt["normalized_count"] == 2
    assert receipt["sqlite_upserted_count"] == 2
    assert len(transport.calls) == 1
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="meeting-topics", db_path=db
    ) == 2
    # The free-text `minutes` content does not appear in canonical storage.
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_json_redacted, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='meeting-topics'"
        ).fetchall()
    finally:
        conn.close()
    for canonical_json, raw_body_persisted in rows:
        assert secret_body_marker not in canonical_json
        assert raw_body_persisted == 0


def test_daily_log_dcrs_apply_persists_with_hash_only_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """daily-log-dcrs is a top-level v1.0 endpoint at
    /daily_construction_report_logs. The notes field (free text) is reduced
    to a SHA-256 hash-only summary; raw text never persisted."""
    _setup_env(monkeypatch)
    db = _db()
    secret_body_marker = "MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE"
    payload = [
        {
            "id": 333675,
            "date": "2016-05-19",
            "datetime": "2016-05-19T12:00:00Z",
            "status": "pending",
            "position": 53253,
            "apprentice_hours": "5.0",
            "foreman_hours": "5.0",
            "journeyman_hours": "5.0",
            "notes": secret_body_marker,
            "vendor": {"id": 161072, "name": "SID Architecture"},
            "trade": {"id": 999, "name": "09 - acoustical panels"},
            "created_at": "2012-10-23T21:39:40Z",
            "updated_at": "2012-10-24T21:39:40Z",
        }
    ]
    transport = _FakeTransport(payload)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="daily-log-dcrs",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["sqlite_upserted_count"] == 1
    assert len(transport.calls) == 1
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_json_redacted, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='daily-log-dcrs'"
        ).fetchall()
    finally:
        conn.close()
    assert rows
    for canonical_json, raw_body_persisted in rows:
        assert secret_body_marker not in canonical_json
        assert "notes_summary" in canonical_json  # hash summary present
        assert "hash_prefix" in canonical_json
        assert raw_body_persisted == 0


# ----------------------------------------------------------------------------
# meeting-detail: list+detail N+1 with PII hashing and nested topic extraction
# ----------------------------------------------------------------------------


def test_meeting_detail_apply_persists_meeting_and_nested_topics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """meeting-detail fetches the meetings list, then issues one detail GET per
    meeting (N+1). The detail payload's meeting_categories[].meeting_topic[]
    items are extracted and upserted under endpoint_id="meeting-topics"."""
    _setup_env(monkeypatch)
    db = _db()
    secret_attendee_email = "should.not.leak@example.com"
    secret_minutes_marker = "MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE"

    list_payload = [
        {"id": 11},
        {"id": 22},
    ]
    detail_11 = {
        "id": 11,
        "title": "Meeting Eleven",
        "starts_at": "2026-03-01T15:00:00Z",
        "ends_at": "2026-03-01T16:00:00Z",
        "time_zone": "UTC",
        "mode": "minutes",
        "is_private": False,
        "description": "Body that must not be persisted as text.",
        "conclusion": "Conclusion that must not be persisted.",
        "remote_meeting_url": "https://zoom.us/j/abc?pwd=SECRET",
        "attendees": [
            {"id": 1, "status": "Present",
             "login_information": {"login": secret_attendee_email, "name": "PII Name"}},
        ],
        "meeting_categories": [
            {
                "id": 999,
                "title": "Items",
                "meeting_topic": [
                    {"id": 7001, "title": "T1", "status": "Open",
                     "minutes": secret_minutes_marker},
                    {"id": 7002, "title": "T2", "status": "Open"},
                ],
            }
        ],
    }
    detail_22 = {
        "id": 22,
        "title": "Meeting Twenty-Two",
        "starts_at": "2026-03-02T15:00:00Z",
        "ends_at": "2026-03-02T16:00:00Z",
        "time_zone": "UTC",
        "mode": "minutes",
        "attendees": [],
        "meeting_categories": [],
    }

    transport = _PathAwareFakeTransport(
        {
            "/rest/v1.1/projects/2525840/meetings/11": [detail_11],
            "/rest/v1.1/projects/2525840/meetings/22": [detail_22],
            "/rest/v1.1/projects/2525840/meetings": list_payload,
        }
    )

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="meeting-detail",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["parent_upserted_count"] == 2
    assert receipt["child_endpoint_id"] == "meeting-topics"
    assert receipt["child_upserted_count"] == 2  # 2 topics from meeting 11
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="meeting-detail", db_path=db
    ) == 2
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="meeting-topics", db_path=db
    ) == 2

    # PII redaction attestation
    conn = sqlite3.connect(str(db))
    try:
        detail_rows = conn.execute(
            "SELECT canonical_json_redacted, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='meeting-detail'"
        ).fetchall()
        topic_rows = conn.execute(
            "SELECT canonical_json_redacted, parent_procore_id, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='meeting-topics'"
        ).fetchall()
    finally:
        conn.close()

    for canonical_json, raw_body_persisted in detail_rows:
        assert secret_attendee_email not in canonical_json
        assert "PII Name" not in canonical_json
        assert "SECRET" not in canonical_json  # remote_meeting_url query stripped
        assert "?" not in canonical_json or "?pwd=" not in canonical_json
        assert raw_body_persisted == 0

    for canonical_json, parent_procore_id, raw_body_persisted in topic_rows:
        assert secret_minutes_marker not in canonical_json
        assert parent_procore_id in {"11", "22"}
        assert raw_body_persisted == 0


# ----------------------------------------------------------------------------
# punch-items: standalone /punch_items endpoint with project_id query param
# ----------------------------------------------------------------------------


def test_punch_items_apply_persists_with_pii_hashed_and_bodies_summarized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    secret_email = "should.not.leak@example.com"
    secret_name = "PII Person Name"
    secret_description = "DETAIL_BODY_MUST_NEVER_APPEAR"
    secret_comment = "COMMENT_BODY_MUST_NEVER_APPEAR"
    payload = [
        {
            "id": 1001,
            "name": "Punch A",
            "status": "Open",
            "priority": "High",
            "due_date": "2026-06-30",
            "created_at": "2026-05-28T10:00:00Z",
            "updated_at": "2026-05-28T10:00:00Z",
            "cost_impact": "yes_known",
            "cost_impact_amount": "250.0",
            "schedule_impact_days": 2,
            "description": secret_description,
            "schedule_risk_reason": "Risk reasoning that must not appear.",
            "location": {"id": 50, "name": "Floor 3", "code": "L3"},
            "trade": {"id": 7, "name": "Electrical", "active": True},
            "ball_in_court": [{"id": 1, "name": secret_name}],
            "assignees": [{"id": 2, "login": secret_email, "name": secret_name}],
            "assignments": [
                {
                    "id": 99,
                    "status": "unresolved",
                    "comment": secret_comment,
                    "login_information": {"id": 2, "login": secret_email, "name": secret_name},
                    "vendor": {"id": 50, "name": "Acme Co"},
                }
            ],
        }
    ]
    transport = _FakeTransport(payload)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="punch-items",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=5,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["sqlite_upserted_count"] == 1
    # Single HTTP call (no N+1)
    assert len(transport.calls) == 1
    # project_id passed as query param (not path placeholder)
    assert transport.calls[0]["params"].get("project_id") == "2525840"

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_json_redacted, review_required, raw_body_persisted "
            "FROM procore_live_records WHERE endpoint_id='punch-items'"
        ).fetchall()
    finally:
        conn.close()
    assert rows
    for canonical_json, review_required, raw_body_persisted in rows:
        assert raw_body_persisted == 0
        assert review_required == 1  # PII bearing -> always review
        assert secret_email not in canonical_json
        assert secret_name not in canonical_json
        assert secret_description not in canonical_json
        assert secret_comment not in canonical_json
        # Structured fields preserved
        assert "cost_impact_amount" in canonical_json
        assert "schedule_impact_days" in canonical_json
        # Hash summaries present
        assert "description_summary" in canonical_json
        assert "schedule_risk_reason_summary" in canonical_json
        # No emails persisted
        assert "@" not in canonical_json
