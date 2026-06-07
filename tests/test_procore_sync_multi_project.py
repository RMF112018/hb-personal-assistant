"""All-project Procore sync tests (the ``"multi"`` KeyError regression + per-project
aggregation). Dry-run uses the real seed registry/contract/auditor (no network);
apply patches the HTTP client. No live/integration markers — default-safe subset.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import hb_assistant.procore.sync as sync_mod
from hb_assistant.cli.main import app
from hb_assistant.procore.auditor import EndpointAuditor
from hb_assistant.procore.errors import ProcoreMappingUnavailable
from hb_assistant.procore.loader import load_procore_projects
from hb_assistant.procore.sync import run_sync

runner = CliRunner()


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _pilot_keys() -> list[str]:
    reg = load_procore_projects()
    return [p.hb_project_key for p in reg.projects if p.status == "pilot"]


def test_all_project_dry_run_succeeds() -> None:
    pilots = _pilot_keys()
    assert len(pilots) >= 2, "fixture needs 2+ mapped pilots to exercise the multi path"

    res = run_sync(project_key=None, dry_run=True, db_path=_temp_db())

    assert res["mode"] == "dry_run"
    assert res["project_scope"] == "multi"
    assert len(res["per_project"]) == len(pilots)
    scopes = [p["project_scope"] for p in res["per_project"]]
    assert sorted(scopes) == sorted(pilots)
    assert "multi" not in scopes  # never the sentinel at the project level


def test_all_project_never_audits_with_multi(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def make_auditor(contract: Any, projects: Any) -> EndpointAuditor:
        inst = EndpointAuditor(contract, projects)
        original = inst.build_audit_run_receipt

        def wrapped(project_key: str, **kw: Any) -> Any:
            captured.append(project_key)
            return original(project_key, **kw)

        inst.build_audit_run_receipt = wrapped  # type: ignore[method-assign]
        return inst

    monkeypatch.setattr(sync_mod, "EndpointAuditor", make_auditor)

    run_sync(project_key=None, dry_run=True, db_path=_temp_db())

    assert "multi" not in captured
    assert captured  # auditor was exercised per project
    assert set(captured) == set(_pilot_keys())


def test_all_project_apply_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.paginate.return_value = [{"id": "r1", "number": "RFI-1", "status": "open"}]
    monkeypatch.setattr(sync_mod, "ProcoreHTTPClient", MagicMock(return_value=mock_client))

    pilots = _pilot_keys()
    res = run_sync(project_key=None, apply=True, db_path=_temp_db())

    assert res["mode"] == "apply"
    assert res["persisted_to_sqlite"] is True
    assert len(res["per_project"]) == len(pilots)
    assert all(p["audit_prerequisite_passed"] for p in res["per_project"])
    # aggregate totals equal the sum of per-project totals
    assert res["total_items_normalized"] == sum(
        p["total_items_normalized"] for p in res["per_project"]
    )


def test_single_project_unchanged() -> None:
    res = run_sync(project_key="tropical", dry_run=True, db_path=_temp_db())

    assert res["mode"] == "dry_run"
    assert res["project_scope"] == "tropical"
    assert len(res["per_project"]) == 1
    assert res["per_project"][0]["project_scope"] == "tropical"
    assert res["audit_prerequisite_passed"] is True
    assert all("redacted_request_envelope" in e for e in res.get("per_endpoint", []))


def test_unknown_project_fails_closed() -> None:
    with pytest.raises(ProcoreMappingUnavailable):
        run_sync(project_key="does-not-exist", dry_run=True, db_path=_temp_db())


def test_unknown_project_cli_clean_error() -> None:
    result = runner.invoke(
        app, ["procore", "sync", "run", "--project", "bogus", "--dry-run", "--json"]
    )
    assert result.exit_code == 2
    assert "unknown hb_project_key" in result.output


def test_dry_run_writes_nothing() -> None:
    res = run_sync(project_key=None, dry_run=True, db_path=_temp_db())
    assert res["persisted_to_sqlite"] is False
    assert res["total_items_normalized"] == 0


def test_apply_requires_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_PROCORE_LIVE", raising=False)
    # non-TTY --apply without --confirm fails closed.
    result = runner.invoke(app, ["procore", "sync", "run", "--apply", "--json"])
    assert result.exit_code == 1
    assert "confirm" in result.output.lower()


def test_apply_requires_live_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_PROCORE_LIVE", raising=False)
    # --apply --confirm but no live gate fails closed before any sync.
    result = runner.invoke(app, ["procore", "sync", "run", "--apply", "--confirm", "--json"])
    assert result.exit_code == 2


def test_no_source_system_writeback(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a: Any, **k: Any) -> Any:  # dry-run must never construct an HTTP client
        raise AssertionError("dry-run constructed a Procore HTTP client")

    monkeypatch.setattr(sync_mod, "ProcoreHTTPClient", _boom)

    res = run_sync(project_key=None, dry_run=True, db_path=_temp_db())
    assert res["guardrails"]["no_procore_writeback"] is True
    assert res["guardrails"]["no_post_put_patch_delete"] is True
