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


def test_rfis_apply_persists_parents_and_replies_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _PathAwareFakeTransport(
        {
            "/rest/v1.0/projects/2525840/rfis/101/replies": [_reply(9001), _reply(9002), _reply(9003)],
            "/rest/v1.0/projects/2525840/rfis/102/replies": [_reply(9101), _reply(9102)],
            # parent path matched last because it's a prefix of the child paths
            "/rest/v1.0/projects/2525840/rfis": _RFI_PAYLOAD,
        }
    )

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
            transport=_PathAwareFakeTransport(
                {
                    "/rest/v1.0/projects/2525840/rfis/101/replies": [_reply(9001), _reply(9002)],
                    "/rest/v1.0/projects/2525840/rfis/102/replies": [_reply(9101)],
                    "/rest/v1.0/projects/2525840/rfis": _RFI_PAYLOAD,
                }
            ),
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


def test_rfis_apply_tolerates_child_404_without_aborting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _PathAwareFakeTransport(
        path_to_payload={
            "/rest/v1.0/projects/2525840/rfis/101/replies": [_reply(9001), _reply(9002)],
            "/rest/v1.0/projects/2525840/rfis": _RFI_PAYLOAD,
        },
        error_paths={"/rest/v1.0/projects/2525840/rfis/102/replies": 404},
    )

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

    # Both parents land; only parent 101's two replies land. Parent 102's
    # child fetch surfaces a 404 -> child_errors_count=1, state="partial_success".
    assert receipt["state"] in {"success", "partial_success"}
    assert receipt["parent_upserted_count"] == 2
    assert receipt["child_upserted_count"] == 2
    assert receipt["child_errors_count"] == 1


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
    transport = _PathAwareFakeTransport(
        {
            "/rest/v1.0/projects/2525840/rfis/101/replies": [reply_with_marker],
            "/rest/v1.0/projects/2525840/rfis/102/replies": [],
            "/rest/v1.0/projects/2525840/rfis": _RFI_PAYLOAD,
        }
    )
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


def test_submittals_apply_persists_parents_and_responses_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _PathAwareFakeTransport(
        {
            "/rest/v1.0/projects/2525840/submittals/201/responses": [
                _submittal_response(8001),
                _submittal_response(8002),
                _submittal_response(8003),
            ],
            "/rest/v1.0/projects/2525840/submittals/202/responses": [
                _submittal_response(8101),
                _submittal_response(8102),
            ],
            # parent path matched last because it's a prefix of the child paths
            "/rest/v1.0/projects/2525840/submittals": _SUBMITTAL_PAYLOAD,
        }
    )

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
            transport=_PathAwareFakeTransport(
                {
                    "/rest/v1.0/projects/2525840/submittals/201/responses": [
                        _submittal_response(8001),
                        _submittal_response(8002),
                    ],
                    "/rest/v1.0/projects/2525840/submittals/202/responses": [
                        _submittal_response(8101),
                    ],
                    "/rest/v1.0/projects/2525840/submittals": _SUBMITTAL_PAYLOAD,
                }
            ),
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


def test_submittals_apply_tolerates_child_404_without_aborting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _PathAwareFakeTransport(
        path_to_payload={
            "/rest/v1.0/projects/2525840/submittals/201/responses": [
                _submittal_response(8001),
                _submittal_response(8002),
            ],
            "/rest/v1.0/projects/2525840/submittals": _SUBMITTAL_PAYLOAD,
        },
        error_paths={"/rest/v1.0/projects/2525840/submittals/202/responses": 404},
    )

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

    assert receipt["state"] in {"success", "partial_success"}
    assert receipt["parent_upserted_count"] == 2
    assert receipt["child_upserted_count"] == 2
    assert receipt["child_errors_count"] == 1


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
    transport = _PathAwareFakeTransport(
        {
            "/rest/v1.0/projects/2525840/submittals/201/responses": [response_with_marker],
            "/rest/v1.0/projects/2525840/submittals/202/responses": [],
            "/rest/v1.0/projects/2525840/submittals": _SUBMITTAL_PAYLOAD,
        }
    )
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
