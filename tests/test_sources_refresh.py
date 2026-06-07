"""Tests for the unified `construction-agent refresh-sources` orchestration command.

The orchestrator imports the heavy Procore/Graph/second-brain surfaces at its own
module namespace, so we patch them there for deterministic, network-free runs. Auth
and external readers are stubbed; the real ``SQLiteMigrator`` is used only for the
auto-migrate test.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

import hb_assistant.source_refresh.orchestrator as orch
from hb_assistant.cli.main import app
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

runner = CliRunner()

CMD = ["construction-agent", "refresh-sources"]

# Value-shaped markers that would indicate a real secret/raw leak. (Deliberately not
# attestation key names like ``no_join_url_persisted``, which legitimately appear.)
FORBIDDEN_RAW = (
    "Bearer ",
    "BEGIN PRIVATE KEY",
    "eyJ",  # JWT prefix
    '"access_token":',
    '"refresh_token":',
    '"client_secret":',
)


def _auth_ready() -> SimpleNamespace:
    return SimpleNamespace(status="env_present", ready_for_live_calls=True, hint="ready")


def _auth_not_ready() -> SimpleNamespace:
    return SimpleNamespace(status="env_absent", ready_for_live_calls=False, hint="login")


class _Project:
    def __init__(self, key: str) -> None:
        self.hb_project_key = key
        self.status = "pilot"


class _Registry:
    def __init__(self) -> None:
        self.projects = [_Project("tropical"), _Project("pga-modern-garage")]


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch all external/heavy surfaces at the orchestrator namespace.

    Defaults: Procore auth ready, no live env, Graph has no token. Returns a dict of
    call recorders so tests can assert what was (not) invoked.
    """
    calls: dict[str, Any] = {"run_sync": [], "calendar": 0, "files": 0}

    monkeypatch.setattr(orch, "check_auth_status", _auth_ready)
    monkeypatch.setattr(orch, "load_procore_projects", lambda: _Registry())
    monkeypatch.setattr(orch, "live_env_active", lambda: False)
    monkeypatch.setattr(orch, "assert_live_mapping_strict", lambda reg, keys: None)

    def fake_run_sync(**kw: Any) -> dict[str, Any]:
        calls["run_sync"].append(kw)
        return {
            "total_items_normalized": 0,
            "persisted_to_sqlite": bool(kw.get("apply")),
            "audit_prerequisite_passed": True,
            "per_endpoint": [],
            "category_counts": {},
            "redacted_errors": [],
        }

    monkeypatch.setattr(orch, "run_sync", fake_run_sync)

    monkeypatch.setattr(
        orch,
        "build_approved_source_manifest",
        lambda db: {
            "status": "empty",
            "approved_ref_count": 0,
            "approved_family_count": 0,
            "manifest_hash": "h0",
        },
    )
    monkeypatch.setattr(
        orch, "build_approved_source_manifest_proof", lambda **k: {"proof_passed": True}
    )
    monkeypatch.setattr(
        orch,
        "build_coverage_parity_closeout",
        lambda db, **k: {"closeout_ok": True, "sub_proofs_passed": {}},
    )
    monkeypatch.setattr(
        orch,
        "build_vector_index_dry_run",
        lambda db: {
            "status": "dry_run",
            "planned_chunk_count": 0,
            "ready_to_apply": False,
            "vectors_persisted_to_sqlite": False,
        },
    )
    monkeypatch.setattr(
        orch,
        "build_vector_index_apply",
        lambda db: {
            "status": "applied",
            "applied_item_count": 3,
            "vector_store_location": "/tmp/vs",
            "vectors_persisted_to_sqlite": False,
        },
    )
    monkeypatch.setattr(
        orch, "build_no_raw_vector_index_proof", lambda db, **k: {"proof_passed": True}
    )
    monkeypatch.setattr(
        orch,
        "build_daily_brief_packet_v2",
        lambda **k: {
            "packet_version": "DailyBriefHandoffPacketV2",
            "status": "ok",
            "brief_date": k.get("brief_date"),
        },
    )
    monkeypatch.setattr(
        orch, "build_daily_brief_packet_v2_proof", lambda **k: {"proof_passed": True}
    )
    monkeypatch.setattr(
        orch, "build_daily_brief_v2_quality_proof", lambda **k: {"proof_passed": True}
    )
    monkeypatch.setattr(orch, "build_no_raw_mcp_access_proof", lambda **k: {"proof_passed": True})
    monkeypatch.setattr(orch, "build_no_mcp_writeback_proof", lambda **k: {"proof_passed": True})

    # Graph: no delegated token by default; mail summary is local-only.
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator, "_graph_status", lambda self: {"token_type": "none"}
    )
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator,
        "_graph_mail_thread_summary",
        lambda self, dry_run: {
            "status": "ok",
            "mode": "dry_run" if dry_run else "apply",
            "local_only": True,
            "summarized": 0,
            "considered": 0,
            "persisted": not dry_run,
        },
    )

    def _cal(self: Any, dry_run: bool) -> dict[str, Any]:
        calls["calendar"] += 1
        return {"status": "ok", "mode": "dry_run", "events_indexed": 2}

    def _files(self: Any, dry_run: bool) -> dict[str, Any]:
        calls["files"] += 1
        return {"status": "ok", "mode": "dry_run", "items_indexed": 4}

    monkeypatch.setattr(orch.SourceRefreshOrchestrator, "_graph_calendar", _cal)
    monkeypatch.setattr(orch.SourceRefreshOrchestrator, "_graph_files", _files)
    return calls


def _run(args: list[str]) -> tuple[int, dict[str, Any]]:
    result = runner.invoke(app, CMD + args)
    payload: dict[str, Any] = {}
    if result.stdout.strip().startswith("{"):
        payload = json.loads(result.stdout)
    return result.exit_code, payload


# --- gating / validation (no orchestrator needed) --------------------------------


def test_apply_requires_confirm() -> None:
    result = runner.invoke(app, CMD + ["--apply", "--json"])
    assert result.exit_code == 1
    assert "requires --confirm" in result.output


def test_procore_only_graph_only_exclusive() -> None:
    result = runner.invoke(app, CMD + ["--procore-only", "--graph-only", "--json"])
    assert result.exit_code == 2


def test_all_with_only_flag_rejected() -> None:
    result = runner.invoke(app, CMD + ["--all", "--procore-only", "--json"])
    assert result.exit_code == 2


def test_invalid_date_rejected() -> None:
    result = runner.invoke(app, CMD + ["--date", "2026-13-99", "--json"])
    assert result.exit_code == 2


# --- orchestration behavior ------------------------------------------------------


def test_dry_run_writes_nothing(patched: dict[str, Any]) -> None:
    code, payload = _run(["--all", "--json"])
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    total = payload["sqlite_upsert_summary"]["total"]
    assert total["inserted"] == 0 and total["updated"] == 0
    # every run_sync invocation was a plan (no apply)
    assert patched["run_sync"], "procore plan should have run"
    assert all(c["dry_run"] and not c["apply"] for c in patched["run_sync"])


def test_procore_auth_failure_blocks_procore(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "check_auth_status", _auth_not_ready)
    code, payload = _run(["--all", "--apply", "--confirm", "--json"])
    assert code == 1
    assert payload["status"] == "degraded"
    assert payload["procore_sync_summary"]["status"] == "blocked_auth_not_ready"
    assert patched["run_sync"] == [], "no live read when auth not ready"
    assert "procore auth login" in payload["next_operator_action"]


def test_graph_auth_failure_blocks_graph(patched: dict[str, Any]) -> None:
    code, payload = _run(["--all", "--apply", "--confirm", "--json"])
    graph = payload["graph_sync_summary"]
    assert graph["status"] == "blocked_auth_not_ready"
    assert graph["families"]["calendar_event_index"]["status"] == "blocked_auth_not_ready"
    assert graph["families"]["files"]["status"] == "blocked_auth_not_ready"
    # live Graph indexers were never invoked
    assert patched["calendar"] == 0 and patched["files"] == 0
    assert payload["status"] == "degraded"


def test_partial_failure_degraded(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(db: str, **k: Any) -> dict[str, Any]:
        raise RuntimeError("coverage exploded")

    monkeypatch.setattr(orch, "build_coverage_parity_closeout", boom)
    code, payload = _run(["--all", "--json"])
    assert payload["status"] == "degraded"
    stages = [f["stage"] for f in payload["failures"]]
    assert "rebuild.coverage_parity" in stages
    # other rebuild work still completed
    assert payload["daily_brief_v2_summary"]["status"] == "ok"
    assert payload["retrieval_rebuild_summary"]["approved_sources"]["status"] == "empty"


def test_no_source_writeback(patched: dict[str, Any]) -> None:
    _, payload = _run(["--all", "--json"])
    g = payload["guardrails"]
    for flag in (
        "no_procore_writeback",
        "no_m365_writeback",
        "no_raw_email_or_calendar_body",
        "no_join_url_persisted",
        "no_raw_procore_payload",
        "no_prompts_or_model_responses_persisted",
        "no_vectors_in_sqlite",
        "mcp_exposure_unchanged",
    ):
        assert g[flag] is True


def test_sqlite_upsert_counts_reported_apply(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)

    def fake_run_sync(**kw: Any) -> dict[str, Any]:
        patched["run_sync"].append(kw)
        return {
            "total_items_normalized": 5,
            "persisted_to_sqlite": True,
            "audit_prerequisite_passed": True,
            "per_endpoint": [],
            "redacted_errors": [],
        }

    monkeypatch.setattr(orch, "run_sync", fake_run_sync)
    _, payload = _run(["--all", "--apply", "--confirm", "--json"])
    # two pilot projects × 5 normalized rows persisted
    assert payload["sqlite_upsert_summary"]["procore"]["inserted"] == 10
    assert payload["sqlite_upsert_summary"]["total"]["inserted"] == 10
    assert payload["procore_sync_summary"]["status"] == "ok"


def test_skip_vector(patched: dict[str, Any]) -> None:
    _, payload = _run(["--all", "--skip-vector", "--json"])
    assert payload["vector_rebuild_summary"]["status"] == "skipped"


def test_skip_daily_brief_proof(patched: dict[str, Any]) -> None:
    _, payload = _run(["--all", "--skip-daily-brief-proof", "--json"])
    assert payload["daily_brief_v2_summary"]["status"] == "skipped"


def test_procore_only_skips_graph(patched: dict[str, Any]) -> None:
    _, payload = _run(["--procore-only", "--json"])
    assert payload["graph_sync_summary"]["status"] == "skipped"
    assert payload["graph_sync_summary"]["reason"] == "procore_only"


def test_graph_only_skips_procore(patched: dict[str, Any]) -> None:
    _, payload = _run(["--graph-only", "--json"])
    assert payload["procore_sync_summary"]["status"] == "skipped"
    assert payload["procore_sync_summary"]["reason"] == "graph_only"


def test_v2_packet_generated_after_refresh(patched: dict[str, Any]) -> None:
    _, payload = _run(["--all", "--date", "2026-06-07", "--json"])
    db = payload["daily_brief_v2_summary"]
    assert db["packet_version"] == "DailyBriefHandoffPacketV2"
    assert db["brief_date"] == "2026-06-07"


def test_no_raw_content_in_output(patched: dict[str, Any]) -> None:
    result = runner.invoke(app, CMD + ["--all", "--json"])
    for token in FORBIDDEN_RAW:
        assert token not in result.output


def test_redact_json_scrubs_tokens() -> None:
    payload = {"access_token": "abc", "nested": {"refresh_token": "xyz", "ok": 1}}
    scrubbed = orch.SourceRefreshOrchestrator.redact_json(payload)
    assert "abc" in scrubbed  # value remains; key label is what gets scrubbed
    assert "access_token" not in scrubbed
    assert "refresh_token" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_auto_migrate_under_apply_confirm(patched: dict[str, Any]) -> None:
    db_path = PathPolicy().get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Fresh DB starts unmigrated.
    assert SQLiteMigrator(db_path).current_version() == 0

    _, payload = _run(["--all", "--apply", "--confirm", "--json"])
    assert payload["preflight"]["auto_migrated"] is True
    assert payload["preflight"]["schema_version"] == LATEST_SCHEMA_VERSION
    assert SQLiteMigrator(db_path).current_version() == LATEST_SCHEMA_VERSION


def test_dry_run_does_not_migrate(patched: dict[str, Any]) -> None:
    db_path = PathPolicy().get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    assert SQLiteMigrator(db_path).current_version() == 0
    _run(["--all", "--json"])
    # dry-run never writes schema
    assert SQLiteMigrator(db_path).current_version() == 0
