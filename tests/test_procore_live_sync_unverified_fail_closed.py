"""Phase 04A unverified endpoints must fail closed without touching transport."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.store.migrator import SQLiteMigrator

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


# The three held (live_verified=False) endpoints — Phase 06B Prompt 04 keeps them
# explicitly fail-closed (no live env, no permission change, no path guessing).
_UNVERIFIED_IDS: tuple[str, ...] = (
    "purchase-order-detail-line-items",
    "budget-change-line-items",
    "budget-details",
)


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


@pytest.mark.parametrize("endpoint_id", _UNVERIFIED_IDS)
def test_unverified_endpoint_returns_not_live_verified_receipt(
    monkeypatch: pytest.MonkeyPatch, endpoint_id: str
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-token")

    def _boom(*args: object, **kwargs: object) -> object:  # noqa: ARG001
        raise AssertionError("unverified endpoint must not hit live transport")

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _boom,
    )

    receipt = run_live_sync(
        project_key="tropical",
        endpoint=endpoint_id,
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=5,
        db_path=_db(),
    )

    assert receipt["state"] == "not_live_verified"
    assert receipt["no_live_call_performed"] is True
    assert receipt["request_count"] == 0
    assert receipt["retrieved_count"] == 0
    assert receipt["normalized_count"] == 0
    assert receipt["sqlite_upserted_count"] == 0
    assert receipt["raw_body_persisted"] is False
    assert receipt["secrets_redacted"] is True
    assert "endpoint_unverified_for_live" in receipt["reason_codes"]
    assert receipt["endpoint_id"] == endpoint_id
    assert receipt["http_method"] == "GET"


def test_unknown_endpoint_fails_closed_with_alias_unknown_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-token")
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="totally-bogus-endpoint",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=_db(),
    )
    assert receipt["state"] == "fail_closed_unsupported"
    assert "endpoint_alias_unknown" in receipt["reason_codes"]
    assert receipt["no_live_call_performed"] is True


def test_missing_confirm_live_get_blocks_verified_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-token")
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=False,
        db_path=_db(),
    )
    assert receipt["state"] == "gate_blocked"
    assert "confirm_live_get_required" in receipt["reason_codes"]
    assert receipt["no_live_call_performed"] is True


def test_missing_live_env_blocks_verified_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=_db(),
    )
    assert receipt["state"] == "gate_blocked"
    assert "live_env_not_set" in receipt["reason_codes"]
    assert receipt["no_live_call_performed"] is True
