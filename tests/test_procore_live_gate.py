"""Tests for the Phase 04A Prompt 01 HB_PROCORE_LIVE env-var gate.

Covers helper semantics (exact ``"1"`` enabler), CLI fail-closed behavior
on ``audit execute`` and ``sync run --apply`` when the env-var is absent,
and the strict mapping check at the live boundary. No live HTTP. All
env-var manipulation goes through ``monkeypatch``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.procore import (
    LIVE_ENV_ENABLER,
    LIVE_ENV_VAR,
    LiveEnvNotSet,
    assert_live_mapping_strict,
    direct_live_project_eligibility,
    live_env_active,
    require_live_env,
)
from hb_assistant.procore.errors import ProcoreAPIError
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.procore.models import (
    ProcoreProjectMapping,
    ProcoreProjectsRegistry,
)
from hb_assistant.store.migrator import SQLiteMigrator

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


# ----------------------------------------------------------------------------
# live_env_active / require_live_env
# ----------------------------------------------------------------------------


def test_live_env_active_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    assert live_env_active() is False


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "on", "TRUE", "1 ", " 1"])
def test_live_env_active_false_for_non_enabler_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, value)
    assert live_env_active() is False


def test_live_env_active_true_only_for_exact_enabler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    assert live_env_active() is True


def test_require_live_env_raises_when_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    with pytest.raises(LiveEnvNotSet) as exc_info:
        require_live_env(command="procore audit execute")
    assert exc_info.value.code == "live_env_not_set"
    assert "HB_PROCORE_LIVE" in exc_info.value.message
    assert exc_info.value.command == "procore audit execute"


def test_require_live_env_silent_when_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    require_live_env(command="procore sync run --apply")


# ----------------------------------------------------------------------------
# assert_live_mapping_strict
# ----------------------------------------------------------------------------


def _registry(rows: list[tuple[str, str, str]]) -> ProcoreProjectsRegistry:
    return ProcoreProjectsRegistry(
        company_id="5280",
        projects=[
            ProcoreProjectMapping(
                hb_project_key=key,
                procore_project_id=pid,
                procore_project_name="x" if pid else "",
                status=status,
            )
            for key, pid, status in rows
        ],
    )


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "procore-live-gate.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    return db


class _Response:
    status_code = 200
    headers: dict[str, str] = {}
    text = ""

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _Transport:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
    ) -> _Response:
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers), "params": dict(params or {})}
        )
        if len(self.calls) == 1:
            return _Response(self.payload)
        return _Response([])


def test_assert_live_mapping_strict_passes_for_live_refresh_eligible_statuses() -> None:
    reg = _registry(
        [
            ("tropical", "2525840", "pilot"),
            ("pga-modern-garage", "2091445", "active"),
        ]
    )
    assert_live_mapping_strict(reg, ["tropical", "pga-modern-garage"])


def test_assert_live_mapping_strict_rejects_pending() -> None:
    reg = _registry(
        [
            ("tropical", "2525840", "pilot"),
            ("hilltop", "", "pending"),
        ]
    )
    with pytest.raises(ProcoreAPIError) as exc_info:
        assert_live_mapping_strict(reg, ["tropical", "hilltop"])
    assert exc_info.value.code == "live_mapping_strict_violation"
    assert "hilltop" in exc_info.value.message


def test_assert_live_mapping_strict_rejects_unknown_key() -> None:
    reg = _registry([("tropical", "2525840", "pilot")])
    with pytest.raises(ProcoreAPIError) as exc_info:
        assert_live_mapping_strict(reg, ["does-not-exist"])
    assert "unknown_key" in exc_info.value.message


def test_assert_live_mapping_strict_aggregates_multiple_offenders() -> None:
    reg = _registry(
        [
            ("tropical", "2525840", "pilot"),
            ("hilltop", "", "pending"),
        ]
    )
    with pytest.raises(ProcoreAPIError) as exc_info:
        assert_live_mapping_strict(reg, ["hilltop", "does-not-exist"])
    assert "hilltop" in exc_info.value.message
    assert "does-not-exist" in exc_info.value.message


def test_direct_live_project_eligibility_accepts_configured_project_with_valid_id() -> None:
    reg = _registry([("caretta", "2145250", "deprecated")])
    result = direct_live_project_eligibility(reg, "caretta")

    assert result.ok is True
    assert result.procore_project_id == "2145250"
    assert result.reason_code is None


def test_direct_live_project_eligibility_rejects_unmapped_project() -> None:
    reg = _registry([("caretta", "2145250", "pilot")])
    result = direct_live_project_eligibility(reg, "missing-project")

    assert result.ok is False
    assert result.procore_project_id is None
    assert result.reason_code == "project_not_mapped"


def test_direct_live_project_eligibility_rejects_missing_project_id() -> None:
    reg = _registry([("caretta", "", "pending")])
    result = direct_live_project_eligibility(reg, "caretta")

    assert result.ok is False
    assert result.procore_project_id is None
    assert result.reason_code == "project_missing_procore_project_id"


def test_direct_live_sync_allows_mapped_non_tropical_prime_contracts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    monkeypatch.setattr(
        "hb_assistant.procore.live_sync.load_procore_projects",
        lambda: _registry([("caretta", "2145250", "deprecated")]),
    )
    transport = _Transport([{"id": 101, "show_line_items_to_non_admins": True}])

    receipt = run_live_sync(
        project_key="caretta",
        endpoint="prime-contracts",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=2,
        max_items=20,
        db_path=_fresh_db(tmp_path),
        transport=transport,
    )

    assert transport.calls
    assert receipt["transport_attempted"] is True
    assert receipt["project_eligibility"] == "ok"
    assert receipt["endpoint_eligibility"] == "ok"
    assert receipt["operator_live_authorization"] == "ok"
    assert "mapping_not_live_eligible" not in receipt["reason_codes"]
    assert receipt["procore_project_id"] == "2145250"


def test_direct_live_sync_allows_mapped_non_tropical_punch_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    monkeypatch.setattr(
        "hb_assistant.procore.live_sync.load_procore_projects",
        lambda: _registry([("caretta", "2145250", "deprecated")]),
    )
    transport = _Transport([{"id": 202, "status": "open"}])

    receipt = run_live_sync(
        project_key="caretta",
        endpoint="punch-items",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=2,
        max_items=20,
        db_path=_fresh_db(tmp_path),
        transport=transport,
    )

    assert transport.calls
    assert receipt["transport_attempted"] is True
    assert receipt["project_eligibility"] == "ok"
    assert receipt["endpoint_eligibility"] == "ok"
    assert receipt["operator_live_authorization"] == "ok"
    assert "mapping_not_live_eligible" not in receipt["reason_codes"]


def test_direct_live_sync_rejects_unmapped_project_before_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    monkeypatch.setattr(
        "hb_assistant.procore.live_sync.load_procore_projects",
        lambda: _registry([("caretta", "2145250", "pilot")]),
    )
    transport = _Transport([{"id": 101}])

    receipt = run_live_sync(
        project_key="missing-project",
        endpoint="prime-contracts",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=_fresh_db(tmp_path),
        transport=transport,
    )

    assert transport.calls == []
    assert receipt["transport_attempted"] is False
    assert receipt["project_eligibility"] == "failed"
    assert "project_not_mapped" in receipt["reason_codes"]
    assert "mapping_not_live_eligible" not in receipt["reason_codes"]


def test_direct_live_sync_rejects_mapped_project_missing_project_id_before_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    monkeypatch.setattr(
        "hb_assistant.procore.live_sync.load_procore_projects",
        lambda: _registry([("caretta", "", "pending")]),
    )
    transport = _Transport([{"id": 101}])

    receipt = run_live_sync(
        project_key="caretta",
        endpoint="prime-contracts",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=_fresh_db(tmp_path),
        transport=transport,
    )

    assert transport.calls == []
    assert receipt["transport_attempted"] is False
    assert receipt["project_eligibility"] == "failed"
    assert "project_missing_procore_project_id" in receipt["reason_codes"]
    assert "mapping_not_live_eligible" not in receipt["reason_codes"]


def test_direct_live_sync_rejects_budget_details_before_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    monkeypatch.setattr(
        "hb_assistant.procore.live_sync.load_procore_projects",
        lambda: _registry([("caretta", "2145250", "deprecated")]),
    )
    transport = _Transport([{"id": 101}])

    receipt = run_live_sync(
        project_key="caretta",
        endpoint="budget-details",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=_fresh_db(tmp_path),
        transport=transport,
    )

    assert transport.calls == []
    assert receipt["transport_attempted"] is False
    assert receipt["endpoint_eligibility"] == "failed"
    assert "endpoint_not_live_eligible" in receipt["reason_codes"]
    assert "mapping_not_live_eligible" not in receipt["reason_codes"]


def test_direct_live_sync_reports_operator_authorization_failure_before_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    monkeypatch.setattr(
        "hb_assistant.procore.live_sync.load_procore_projects",
        lambda: _registry([("caretta", "2145250", "pilot")]),
    )
    transport = _Transport([{"id": 101}])

    receipt = run_live_sync(
        project_key="caretta",
        endpoint="prime-contracts",
        apply=True,
        sqlite_only=True,
        confirm_live_get=False,
        db_path=_fresh_db(tmp_path),
        transport=transport,
    )

    assert transport.calls == []
    assert receipt["transport_attempted"] is False
    assert receipt["operator_live_authorization"] == "failed"
    assert {"live_env_not_set", "confirm_live_get_required"} <= set(receipt["reason_codes"])
    assert "mapping_not_live_eligible" not in receipt["reason_codes"]


# ----------------------------------------------------------------------------
# CLI wire-up: gate blocks audit execute / sync run --apply without env var
# ----------------------------------------------------------------------------


def test_cli_audit_execute_blocks_without_live_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "audit", "execute", "--project", "tropical", "--confirm"],
        catch_exceptions=False,
    )
    assert res.exit_code == 2
    assert "live_env_not_set" in res.output.lower() or "hb_procore_live" in res.output.lower()


def test_cli_audit_execute_blocks_with_non_enabler_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, "true")
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "audit", "execute", "--project", "tropical", "--confirm"],
        catch_exceptions=False,
    )
    assert res.exit_code == 2


def test_cli_sync_run_apply_blocks_without_live_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "sync", "run", "--apply", "--confirm", "--project", "tropical"],
        catch_exceptions=False,
    )
    assert res.exit_code == 2
    assert "live_env_not_set" in res.output.lower() or "hb_procore_live" in res.output.lower()


def test_cli_sync_run_dry_run_default_unaffected_by_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default dry-run path must not require the live env var."""
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "sync", "run", "--project", "tropical", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    assert "live_env_not_set" not in res.output.lower()


def test_live_env_and_live_enabled_still_require_confirm_live_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "sync",
            "--project",
            "tropical",
            "--endpoint",
            "rfis",
            "--apply",
            "--sqlite-only",
            "--max-pages",
            "3",
            "--max-items",
            "100",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 3
    assert "confirm_live_get_required" in res.output


def test_live_sync_unverified_endpoint_fails_closed_without_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unverified canonical endpoints must return not_live_verified without
    touching the live transport, even when every other gate is satisfied.

    After Phase 04A closeout, all 16 canonical endpoints are verified, so the
    test temporarily flips one adapter's live_verified flag to False to
    exercise the fail-closed contract. This locks in the orchestrator's
    behavior for any future unverified endpoint additions.
    """
    from dataclasses import replace

    from hb_assistant.procore import endpoints as ep_registry

    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    called = {"hit": False}

    def _boom(*args: object, **kwargs: object) -> object:  # noqa: ARG001
        called["hit"] = True
        raise AssertionError("transport must not be invoked for unverified endpoint")

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _boom,
    )

    base = ep_registry.get("meeting-topics")
    assert base is not None
    demoted = replace(base, live_verified=False)
    monkeypatch.setitem(ep_registry._BY_ID, "meeting-topics", demoted)
    if base.legacy_endpoint_alias:
        monkeypatch.setitem(ep_registry._BY_LEGACY, base.legacy_endpoint_alias, demoted)

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "sync",
            "--project",
            "tropical",
            "--endpoint",
            "meeting-topics",
            "--apply",
            "--sqlite-only",
            "--max-pages",
            "1",
            "--max-items",
            "10",
            "--confirm-live-get",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert called["hit"] is False
    assert res.exit_code == 2
    payload = json.loads(res.output)
    assert payload["state"] == "not_live_verified"
    assert payload["no_live_call_performed"] is True
    assert payload["request_count"] == 0
    assert "endpoint_unverified_for_live" in payload["reason_codes"]


def test_live_sync_phase05_financial_endpoint_fails_closed_without_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A still-unverified Phase 05 financial endpoint (budget-details — the permanent
    non-routable sentinel) must fail closed with no transport even when every gate is
    satisfied — no artificial demotion. (Many financial endpoints were live-promoted
    2026-05-29; 12 remain fail-closed: budget-details + 404/403 paths.)"""
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    called = {"hit": False}

    def _boom(*args: object, **kwargs: object) -> object:  # noqa: ARG001
        called["hit"] = True
        raise AssertionError("transport must not be invoked for unverified endpoint")

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _boom,
    )

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "sync",
            "--project",
            "tropical",
            "--endpoint",
            "budget-details",
            "--apply",
            "--sqlite-only",
            "--max-pages",
            "1",
            "--max-items",
            "10",
            "--confirm-live-get",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert called["hit"] is False
    assert res.exit_code == 2
    payload = json.loads(res.output)
    assert payload["state"] == "not_live_verified"
    assert payload["no_live_call_performed"] is True
    assert payload["request_count"] == 0
    assert "endpoint_unverified_for_live" in payload["reason_codes"]


def test_live_endpoints_list_emits_canonical_phase04a_rows() -> None:
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "live", "endpoints", "list", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    rows = payload.get("endpoints", [])
    rfis = next(r for r in rows if r["endpoint_id"] == "rfis")
    assert rfis["command_endpoint"] == "rfis"
    assert rfis["legacy_endpoint_alias"] == "list-rfis"
    assert rfis["live_verified"] is True
    topics_row = next(r for r in rows if r["endpoint_id"] == "meeting-topics")
    assert topics_row["live_verified"] is True
    # Phase 04A + meeting-detail + punch-items + schedules + activities +
    # + daily-log resolution (weather v1.1 path + accident/dumpster/
    # safety-violation/visitor): all 27 operational endpoints are
    # live-verified. inspection-sections and
    # inspection-items use the project-scoped flat list endpoints supplied
    # by the operator on 2026-05-29 (/checklist/list_sections v1.0 and
    # /checklist/list_items v1.1).
    #
    # Phase 05 appended 32 financial / contract-control shells. 20 were live-promoted on
    # 2026-05-29 after bounded smokes whose payloads matched the normalizer + projection:
    # the parentless contracts/billing/rfq/change-event/budget set, the remaining
    # parentless parents (prime/commitment change orders, purchase-order contracts), and
    # the N+1 children (prime/commitment line items + attachments, CO line items,
    # change-event comments, commitment compliance). The remaining 12 stay
    # live_verified=False (fail-closed): child paths that 404 against the live API
    # (PO/requisition/rfq/budget-view children), payment-applications (404, nested path),
    # budget-change-line-items (403 forbidden), and the budget-details sentinel. So the
    # list is now 56 verified + 3 unverified = 59 rows. Operator-supplied shapes unblocked
    # payment-applications (flat list) and rfq-responses/quotes (contract_id query param). The
    # 3 still fail-closed: purchase-order-detail-line-items (sub-resource 404s for sampled POs),
    # budget-change-line-items (403 forbidden — needs a Procore permission grant), budget-details
    # (non-routable sentinel).
    verified_rows = [r for r in rows if r["live_verified"]]
    unverified_rows = [r for r in rows if not r["live_verified"]]
    assert len(verified_rows) == 56
    assert len(unverified_rows) == 3
    assert len(rows) == 59
