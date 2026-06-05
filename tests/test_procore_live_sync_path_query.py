"""Phase 06B Prompt 02: live-sync path / query param construction hardening.

Pure-function coverage of the five required path/query scenarios plus an integration
regression proving the top-level query-param fix (path-scoped endpoints no longer get a
redundant ?project_id=). No live Procore; fake transport only.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.endpoints import get as get_adapter
from hb_assistant.procore.live_sync import (
    _api_version,
    _child_query_params,
    _project_id_query_params,
    _request_classification,
    _resolve_child_path,
    _resolve_path,
    run_live_sync,
)
from hb_assistant.store.migrator import SQLiteMigrator

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_PID = "2525840"  # synthetic pilot project id (not a secret)


# --- Scenario 1: path contains {project_id} (project-scoped) ---------------------------
def test_project_scoped_path_substitutes_and_omits_query_param() -> None:
    rfis = get_adapter("rfis")
    resolved = _resolve_path(rfis, _PID)
    assert resolved == "/rest/v1.0/projects/2525840/rfis"
    assert "{project_id}" not in resolved
    # project_id is a path segment -> NOT added as a query param (the bug fix).
    assert _project_id_query_params(rfis.path_template, _PID) == {}


# --- Scenario 2: flat endpoint requiring project_id as a query param --------------------
@pytest.mark.parametrize("endpoint_id", ["punch-items", "payment-applications"])
def test_flat_endpoint_carries_project_id_query_param(endpoint_id: str) -> None:
    adapter = get_adapter(endpoint_id)
    assert "{project_id}" not in adapter.path_template
    assert _project_id_query_params(adapter.path_template, _PID) == {"project_id": _PID}


# --- Scenario 3: v2.0 company/project path ---------------------------------------------
def test_v2_company_project_path_substitutes_both_and_omits_query_param() -> None:
    schedules = get_adapter("schedules")
    assert _api_version(schedules.path_template) == "v2.0"
    resolved = _resolve_path(schedules, _PID)
    assert "{company_id}" not in resolved and "{project_id}" not in resolved
    assert f"/projects/{_PID}/schedules" in resolved
    # project_id is in the path -> no redundant query param.
    assert _project_id_query_params(schedules.path_template, _PID) == {}


# --- Scenario 4: N+1 child path with parent id -----------------------------------------
def test_n1_child_path_substitutes_parent_token() -> None:
    rfi_responses = get_adapter("rfi-responses")
    assert rfi_responses.parent_record_id_field == "rfi_id"
    resolved = _resolve_child_path(rfi_responses, _PID, "456")
    assert resolved == "/rest/v1.0/projects/2525840/rfis/456/replies"
    assert "{" not in resolved


# --- Scenario 5: child endpoint requiring an extra parent-derived query param ----------
def test_child_query_params_include_parent_derived_contract_id() -> None:
    rfq_responses = get_adapter("rfq-responses")
    parent_summary = {"id": 9, "commitment_contract_id": "701973"}
    params = _child_query_params(rfq_responses, _PID, parent_summary)
    assert params is not None
    assert params.get("contract_id") == "701973"
    # rfq children carry a flat template -> project_id also travels as a query param.
    assert params.get("project_id") == _PID


def test_child_query_params_without_extra_parent_field_is_none_or_minimal() -> None:
    # A path-scoped child (project_id in path, no extra parent param) needs no query params.
    rfi_responses = get_adapter("rfi-responses")
    assert "{project_id}" in rfi_responses.path_template
    assert _child_query_params(rfi_responses, _PID, {"id": 1}) is None


# --- Request classification (receipt) is secret-free -----------------------------------
def test_request_classification_is_redacted_and_template_derived() -> None:
    schedules = _request_classification(get_adapter("schedules"))
    assert schedules == {
        "api_version": "v2.0",
        "path_scope": "company_project",
        "project_id_param": "path",
        "n_plus_1": False,
        "path_template_redacted": "/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules",
    }
    punch = _request_classification(get_adapter("punch-items"))
    assert punch is not None
    assert punch["path_scope"] == "flat" and punch["project_id_param"] == "query"
    assert _request_classification(None) is None
    # the classification never contains resolved ids, tokens, or query values
    assert "{project_id}" in schedules["path_template_redacted"]


def test_api_version_handles_unresolved_sentinel() -> None:
    assert _api_version("unresolved:budget-details") == "unresolved"


# --- Integration regression: the top-level fix in the real run_live_sync flow ----------
class _FakeResponse:
    def __init__(self, body: Any) -> None:
        self._json_body = body
        self.status_code = 200
        self.headers: Dict[str, str] = {}
        self.text = ""

    def json(self) -> Any:
        return self._json_body


class _RecordingTransport:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, "params": dict(params or {})})
        return _FakeResponse(self.payload if len(self.calls) == 1 else [])


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def test_path_scoped_endpoint_omits_redundant_project_id_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    transport = _RecordingTransport(
        [
            {
                "id": 101,
                "number": "RFI-001",
                "subject": "x",
                "status": "open",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
    )
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=5,
        db_path=_db(),
        transport=transport,
    )
    assert receipt["state"] == "success"
    # rfis is path-scoped (/projects/{project_id}/rfis) -> NO project_id query param.
    assert "project_id" not in transport.calls[0]["params"]
    # receipt carries the redacted request classification.
    assert receipt["request_classification"]["api_version"] == "v1.0"
    assert receipt["request_classification"]["project_id_param"] == "path"
