"""Tests for the unified `construction-agent refresh-sources` orchestration command.

The orchestrator imports the heavy Procore/Graph/second-brain surfaces at its own
module namespace, so we patch them there for deterministic, network-free runs. Auth
and external readers are stubbed; the real ``SQLiteMigrator`` is used only for the
auto-migrate test.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

import hb_assistant.source_refresh.orchestrator as orch
from hb_assistant.cli.main import app
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.calendar.event_indexer import CalendarEventIndexer
from hb_assistant.construction.email.message_indexer import EmailMessageIndexer
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.graph.calendar_readonly_client import ReadOnlyCalendarClient
from hb_assistant.graph.mail_readonly_client import ReadOnlyMailClient
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
    def __init__(self, key: str, status: str = "pilot", project_id: str = "2525840") -> None:
        self.hb_project_key = key
        self.status = status
        self.procore_project_id = project_id


class _Registry:
    def __init__(self) -> None:
        self.projects = [
            _Project("tropical", "pilot", "2525840"),
            _Project("pga-modern-garage", "active", "2091445"),
        ]


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch all external/heavy surfaces at the orchestrator namespace.

    Defaults: Procore auth ready, no live env, Graph has no token. Returns a dict of
    call recorders so tests can assert what was (not) invoked.
    """
    calls: dict[str, Any] = {
        "run_live_sync": [],
        "budget_detail_read_model": [],
        "calendar": 0,
        "files": 0,
    }

    monkeypatch.setattr(orch, "check_auth_status", _auth_ready)
    monkeypatch.setattr(orch, "load_procore_projects", lambda: _Registry())
    monkeypatch.setattr(orch, "live_env_active", lambda: False)
    monkeypatch.setattr(orch, "assert_live_mapping_strict", lambda reg, keys: None)

    def fake_run_live_sync(**kw: Any) -> dict[str, Any]:
        # The orchestrator only calls run_live_sync on the apply+live path; a
        # successful canonical receipt persists into procore_live_records.
        calls["run_live_sync"].append(kw)
        return {
            "endpoint_id": kw.get("endpoint"),
            "sync_run_id": f"{kw.get('project_key')}-{kw.get('endpoint')}",
            "state": "success",
            "status": "success",
            "reason_codes": [],
            "redacted_errors": [],
            "retrieved_count": 5,
            "normalized_count": 5,
            "sqlite_upserted_count": 5,
            "raw_payload_rows_written": 5,
        }

    monkeypatch.setattr(orch, "run_live_sync", fake_run_live_sync)

    def fake_budget_detail_read_model(**kw: Any) -> dict[str, Any]:
        calls["budget_detail_read_model"].append(kw)
        return {
            "ok": True,
            "status": "success",
            "mode": "apply" if kw.get("apply") else "dry_run",
            "inspected_raw_rows": 3,
            "structured_budget_detail_column_rows_inserted_or_updated": 2,
            "structured_budget_detail_row_rows_inserted_or_updated": 4,
            "budget_detail_cell_rows_inserted_or_updated": 12,
            "skipped_missing_record_id": 0,
            "skipped_lower_quality": 0,
            "degraded_parse_errors": 0,
            "local_db_write_performed": bool(kw.get("apply")),
            "external_writeback_performed": 0,
            "raw_payload_body_emitted": False,
        }

    monkeypatch.setattr(orch, "project_budget_detail_read_model", fake_budget_detail_read_model)

    # Stand in for the DB count of current live full-payload rows: every plan endpoint for
    # the (default-registry) projects has landed rows, so success endpoints classify as
    # ok_payload_landed. The real method queries procore_endpoint_raw_payloads.
    def _all_landed(self: Any) -> dict[str, Any]:
        plan = orch.build_daily_refresh_plan()
        by_project_endpoint = {
            key: {pe.canonical_id: 5 for pe in plan}
            for key in ("tropical", "pga-modern-garage")
        }
        by_project = {k: sum(v.values()) for k, v in by_project_endpoint.items()}
        return {"by_project": by_project, "by_project_endpoint": by_project_endpoint}

    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator, "_current_live_full_payload_counts", _all_landed
    )
    monkeypatch.setattr(
        orch,
        "projection_schema_audit",
        lambda **k: {
            "ok": True,
            "runtime_plan_schema_mismatches": 0,
            "missing_table_count": 0,
            "missing_column_count": 0,
            "mismatches": [],
            "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
        },
    )
    monkeypatch.setattr(
        orch,
        "backfill_endpoint_specific_from_raw_payloads",
        lambda **k: {
            "ok": True,
            "primary_rows_written": 11,
            "child_rows_written": 7,
            "raw_full_rows_inspected": 18,
            "degraded_unknown_projection_fields": 0,
            "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
        },
    )
    monkeypatch.setattr(
        orch,
        "projection_audit",
        lambda **k: {
            "ok": True,
            "endpoint_count": 2,
            "unknown_business_field_paths": 0,
            "runtime_plan_schema_mismatches": 0,
            "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
        },
    )

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
    # Dry-run describes the canonical plan WITHOUT any live read (no run_live_sync call).
    assert patched["run_live_sync"] == [], "dry-run must not perform a live read"
    procore = payload["procore_sync_summary"]
    assert procore["status"] == "planned"
    assert procore["persistence_path"] == "procore_live"
    assert procore["endpoint_summary"]["endpoints_planned"] > 0


def test_procore_auth_failure_blocks_procore(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "check_auth_status", _auth_not_ready)
    code, payload = _run(["--all", "--apply", "--confirm", "--json"])
    assert code == 1
    assert payload["status"] == "degraded"
    assert payload["procore_sync_summary"]["status"] == "blocked_auth_not_ready"
    assert patched["run_live_sync"] == [], "no live read when auth not ready"
    assert "procore auth login" in payload["next_operator_action"]


def test_graph_auth_failure_blocks_graph(patched: dict[str, Any]) -> None:
    code, payload = _run(["--all", "--apply", "--confirm", "--json"])
    graph = payload["graph_sync_summary"]
    assert graph["status"] == "blocked_auth_not_ready"
    assert graph["families"]["email_raw_content"]["status"] == "blocked_auth_not_ready"
    assert graph["families"]["calendar_event_index"]["status"] == "blocked_auth_not_ready"
    assert graph["families"]["calendar_raw_content"]["status"] == "blocked_auth_not_ready"
    assert graph["families"]["files"]["status"] == "blocked_auth_not_ready"
    # live Graph indexers were never invoked
    assert patched["calendar"] == 0 and patched["files"] == 0
    assert payload["status"] == "degraded"
    assert payload["email_calendar_projection_summary"]["status"] == "skipped"
    assert (
        payload["email_calendar_projection_summary"]["reason"]
        == "graph_raw_ingestion_blocked_auth_not_ready"
    )


def test_partial_failure_degraded(patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_graph_readonly_clients_expose_no_writeback_methods() -> None:
    forbidden = (
        "send",
        "draft",
        "create",
        "update",
        "delete",
        "patch",
        "post",
        "move",
        "copy",
        "reply",
        "forward",
        "accept",
        "decline",
        "tentative",
        "cancel",
    )
    for cls in (ReadOnlyMailClient, ReadOnlyCalendarClient):
        public = {name for name in dir(cls) if not name.startswith("_")}
        assert not (public & set(forbidden))


def test_sqlite_upsert_counts_reported_apply(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    # patched fixture already stubs run_live_sync to a success receipt (5 upserted each).
    _, payload = _run(["--all", "--apply", "--confirm", "--json"])
    calls = patched["run_live_sync"]
    assert calls, "apply+live should execute the canonical plan"
    expected = 5 * len(calls)
    assert payload["sqlite_upsert_summary"]["procore"]["inserted"] == expected
    assert payload["sqlite_upsert_summary"]["total"]["inserted"] == expected
    assert payload["procore_sync_summary"]["status"] == "ok"
    # Company-level `projects` is fetched once, not once per pilot project.
    projects_calls = [c for c in calls if c.get("endpoint") == "projects"]
    assert len(projects_calls) == 1
    budget_calls = {
        c.get("endpoint"): c
        for c in calls
        if c.get("endpoint")
        in {"budget-views", "budget-detail-columns", "budget-detail-rows"}
    }
    assert set(budget_calls) == {"budget-views", "budget-detail-columns", "budget-detail-rows"}
    for call in budget_calls.values():
        assert call["apply"] is True
        assert call["sqlite_only"] is True
        assert call["confirm_live_get"] is True
        assert call["mode_hint"] == "live_apply"
        assert Path(call["db_path"]).name == "hb-personal-assistant.sqlite"
        assert "path_template" not in call
        assert "parent_id" not in call
        assert "url" not in call
    # daily-log endpoints carry a bounded date window.
    dl_calls = [c for c in calls if str(c.get("endpoint", "")).startswith("daily-log")]
    assert dl_calls and all(c.get("start_date") and c.get("end_date") for c in dl_calls)
    proj = payload["procore_projection_summary"]
    assert proj["status"] == "ok"
    assert proj["selected_project_count"] == 1
    assert {p["project_key"] for p in proj["selected_projects"]} == {"tropical"}
    assert proj["projection_schema_audit"]["ok"] is True
    assert proj["projection_reprocess"]["ok"] is True
    assert proj["projection_reprocess"]["primary_rows_written"] == 11
    assert proj["projection_reprocess"]["child_rows_written"] == 7
    budget_detail = proj["budget_detail_read_model"]
    assert budget_detail["ok"] is True
    assert budget_detail["status"] == "success"
    assert budget_detail["raw_landing_rows_by_endpoint"] == {
        "budget-views": 5,
        "budget-detail-columns": 5,
        "budget-detail-rows": 5,
    }
    assert budget_detail["raw_landing_rows_by_project_endpoint"]["tropical"] == {
        "budget-views": 5,
        "budget-detail-columns": 5,
        "budget-detail-rows": 5,
    }
    assert budget_detail["configured_budget_view_ids_by_project"]["tropical"] == ["713474"]
    assert budget_detail["selected_budget_view_ids_by_project"]["tropical"] == ["713474"]
    assert budget_detail["totals"]["inspected_raw_rows"] == 3
    assert (
        budget_detail["totals"]["structured_budget_detail_column_rows_inserted_or_updated"] == 2
    )
    assert budget_detail["totals"]["structured_budget_detail_row_rows_inserted_or_updated"] == 4
    assert budget_detail["totals"]["budget_detail_cell_rows_inserted_or_updated"] == 12
    assert budget_detail["structured_table_counts"] == {
        "procore_ep_budget_views": 0,
        "procore_ep_budget_detail_columns": 0,
        "procore_ep_budget_detail_rows": 0,
        "procore_ep_budget_detail_row_cells": 0,
    }
    assert budget_detail["guardrails"]["separate_from_projection_reprocess"] is True
    assert budget_detail["guardrails"]["idempotent_reconciliation"] is True
    assert budget_detail["guardrails"]["external_writeback_performed"] == 0
    assert budget_detail["guardrails"]["raw_payload_body_emitted"] is False
    assert budget_detail["guardrails"]["emits_values"] is False
    assert patched["budget_detail_read_model"] == [
        {
            "db_path": Path(budget_calls["budget-views"]["db_path"]),
            "project_key": "tropical",
            "require_live_full": True,
            "apply": True,
        }
    ]
    assert proj["projection_audit"]["ok"] is True
    assert proj["projection_audit"]["unknown_business_field_paths"] == 0
    assert proj["projection_audit"]["runtime_plan_schema_mismatches"] == 0
    blob = json.dumps(budget_detail)
    assert not any(tok in blob for tok in FORBIDDEN_RAW)
    assert "payload_json" not in blob


def test_all_mapped_scope_skips_unsafe_and_selects_pilot_active(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    class MixedRegistry:
        projects = [
            _Project("pilot-job", "pilot", "111"),
            _Project("active-job", "active", "222"),
            _Project("pending-job", "pending", ""),
            _Project("deprecated-job", "deprecated", "333"),
        ]

    monkeypatch.setattr(orch, "load_procore_projects", lambda: MixedRegistry())
    monkeypatch.setattr(orch, "live_env_active", lambda: False)
    opts = orch.RefreshOptions(
        apply=True,
        confirm=True,
        procore_only=True,
        allow_graph_live=False,
        procore_project_scope="all_mapped",
    )
    payload = orch.SourceRefreshOrchestrator().run(options=opts)
    scope = payload["procore_sync_summary"]["project_scope_policy"]
    assert {p["project_key"] for p in scope["selected_projects"]} == {
        "pilot-job",
        "active-job",
    }
    skipped = {p["project_key"]: p["reason"] for p in scope["skipped_projects"]}
    assert skipped["pending-job"] == "status_not_live_refresh_eligible:pending"
    assert skipped["deprecated-job"] == "status_not_live_refresh_eligible:deprecated"


def test_allowlist_unknown_key_blocks_before_live_refresh(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    opts = orch.RefreshOptions(
        apply=True,
        confirm=True,
        procore_only=True,
        allow_graph_live=False,
        procore_project_scope="all_mapped",
        procore_project_keys=("does-not-exist",),
    )
    payload = orch.SourceRefreshOrchestrator().run(options=opts)
    assert payload["status"] == "degraded"
    assert payload["procore_sync_summary"]["status"] == "blocked_project_scope"
    assert patched["run_live_sync"] == []
    assert payload["procore_projection_summary"]["status"] == "blocked_project_scope"


def test_projection_schema_mismatch_prevents_reprocess(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    monkeypatch.setattr(
        orch,
        "projection_schema_audit",
        lambda **k: calls.append("schema")
        or {
            "ok": False,
            "runtime_plan_schema_mismatches": 1,
            "missing_table_count": 0,
            "missing_column_count": 1,
            "mismatches": [{"endpoint_id": "rfis", "table": "procore_ep_rfis", "column": "x"}],
            "guardrails": {"live_calls_disabled": True, "writeback": "none"},
        },
    )
    monkeypatch.setattr(
        orch,
        "backfill_endpoint_specific_from_raw_payloads",
        lambda **k: calls.append("reprocess") or {"ok": True},
    )
    _, payload = _run(["--procore-only", "--apply", "--confirm", "--json"])
    assert payload["status"] == "degraded"
    assert payload["procore_projection_summary"]["status"] == "degraded"
    assert payload["procore_projection_summary"]["reason"] == "schema_parity_broken"
    assert calls == ["schema"]


def test_missing_fresh_raw_payloads_prevent_projection_reprocess(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator,
        "_current_live_full_payload_counts",
        lambda self: {"by_project": {}, "by_project_endpoint": {}},
    )
    called = {"reprocess": False}
    monkeypatch.setattr(
        orch,
        "backfill_endpoint_specific_from_raw_payloads",
        lambda **k: called.__setitem__("reprocess", True) or {"ok": True},
    )
    _, payload = _run(["--procore-only", "--apply", "--confirm", "--json"])
    proj = payload["procore_projection_summary"]
    assert payload["status"] == "degraded"
    assert proj["status"] == "degraded"
    assert proj["reason"] == "raw_full_payload_freshness_missing"
    assert proj["raw_full_payload_freshness"]["missing_fresh_raw_payload_count"] > 0
    assert called["reprocess"] is False


def test_projection_reprocess_failure_still_runs_budget_detail_read_model(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    audit_called = {"projection_audit": False}
    monkeypatch.setattr(
        orch,
        "backfill_endpoint_specific_from_raw_payloads",
        lambda **k: {
            "ok": False,
            "status": "fail_closed_unknown_path",
            "endpoint": "budget-detail-rows",
            "degraded_unknown_projection_fields": 1,
            "unknown_business_field_sample": ["$.sample"],
            "primary_rows_written": 0,
            "child_rows_written": 0,
            "guardrails": {
                "live_calls_disabled": True,
                "writeback": "none",
                "emits_values": False,
            },
        },
    )
    monkeypatch.setattr(
        orch,
        "projection_audit",
        lambda **k: audit_called.__setitem__("projection_audit", True) or {"ok": True},
    )

    _, payload = _run(["--procore-only", "--apply", "--confirm", "--json"])
    proj = payload["procore_projection_summary"]
    budget_detail = proj["budget_detail_read_model"]

    assert payload["status"] == "degraded"
    assert proj["status"] == "degraded"
    assert proj["reason"] == "projection_reprocess_failed"
    assert proj["projection_reprocess"]["ok"] is False
    assert proj["projection_reprocess"]["status"] == "fail_closed_unknown_path"
    assert budget_detail["ok"] is True
    assert budget_detail["status"] == "success"
    assert budget_detail["guardrails"]["external_writeback_performed"] == 0
    assert budget_detail["guardrails"]["raw_payload_body_emitted"] is False
    assert budget_detail["guardrails"]["emits_values"] is False
    assert budget_detail["guardrails"]["counts_only"] is True
    assert set(budget_detail["structured_table_counts"]) == {
        "procore_ep_budget_views",
        "procore_ep_budget_detail_columns",
        "procore_ep_budget_detail_rows",
        "procore_ep_budget_detail_row_cells",
    }
    assert patched["budget_detail_read_model"] == [
        {
            "db_path": Path(patched["run_live_sync"][0]["db_path"]),
            "project_key": "tropical",
            "require_live_full": True,
            "apply": True,
        }
    ]
    stages = [failure["stage"] for failure in payload["failures"]]
    assert "procore_projection.reprocess" in stages
    assert "procore_projection.budget_detail_read_model" not in stages
    assert audit_called["projection_audit"] is False
    blob = json.dumps(budget_detail)
    assert not any(tok in blob for tok in FORBIDDEN_RAW)
    assert "payload_json" not in blob


def test_projection_reprocess_failure_records_budget_detail_failure_too(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    monkeypatch.setattr(
        orch,
        "backfill_endpoint_specific_from_raw_payloads",
        lambda **k: {
            "ok": False,
            "status": "fail_closed_unknown_path",
            "endpoint": "budget-detail-rows",
            "degraded_unknown_projection_fields": 1,
            "primary_rows_written": 0,
            "child_rows_written": 0,
            "guardrails": {
                "live_calls_disabled": True,
                "writeback": "none",
                "emits_values": False,
            },
        },
    )
    monkeypatch.setattr(
        orch,
        "project_budget_detail_read_model",
        lambda **k: patched["budget_detail_read_model"].append(k)
        or {
            "ok": False,
            "status": "schema_unavailable",
            "inspected_raw_rows": 0,
            "structured_budget_detail_column_rows_inserted_or_updated": 0,
            "structured_budget_detail_row_rows_inserted_or_updated": 0,
            "budget_detail_cell_rows_inserted_or_updated": 0,
            "skipped_missing_record_id": 0,
            "skipped_lower_quality": 0,
            "degraded_parse_errors": 0,
            "local_db_write_performed": False,
            "external_writeback_performed": 0,
            "raw_payload_body_emitted": False,
        },
    )

    _, payload = _run(["--procore-only", "--apply", "--confirm", "--json"])
    proj = payload["procore_projection_summary"]
    budget_detail = proj["budget_detail_read_model"]

    assert payload["status"] == "degraded"
    assert proj["status"] == "degraded"
    assert proj["reason"] == "projection_reprocess_failed"
    assert proj["projection_reprocess"]["ok"] is False
    assert proj["projection_reprocess"]["status"] == "fail_closed_unknown_path"
    assert budget_detail["ok"] is False
    assert budget_detail["status"] == "degraded"
    assert budget_detail["projects"][0]["status"] == "schema_unavailable"
    stages = [failure["stage"] for failure in payload["failures"]]
    assert "procore_projection.reprocess" in stages
    assert "procore_projection.budget_detail_read_model" in stages
    assert budget_detail["guardrails"]["external_writeback_performed"] == 0
    assert budget_detail["guardrails"]["raw_payload_body_emitted"] is False
    assert budget_detail["guardrails"]["emits_values"] is False
    assert budget_detail["guardrails"]["counts_only"] is True


def _freshness_db(tmp_path: Any, rows: list[tuple[Any, ...]]) -> Any:
    """A minimal procore_endpoint_raw_payloads table seeded with ``rows``."""
    db_path = tmp_path / "freshness.sqlite"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE procore_endpoint_raw_payloads (
              capture_run_id TEXT,
              project_key TEXT,
              endpoint_key TEXT,
              raw_procore_payload_persisted INTEGER,
              is_current INTEGER,
              source_quality TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO procore_endpoint_raw_payloads VALUES (?, ?, ?, ?, ?, ?)", rows
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_freshness_counts_current_live_full_rows_ignoring_capture_run(tmp_path: Any) -> None:
    # The gate mirrors projection replay: count current live_full_payload rows regardless of
    # capture_run_id (not refreshed on idempotent re-run upserts). Exclude is_current=0,
    # fixture/legacy quality. The "old-run" live row MUST count (no capture_run_id filter).
    db_path = _freshness_db(
        tmp_path,
        [
            ("run-1", "tropical", "rfis", 1, 1, "live_full_payload"),
            ("run-1", "tropical", "rfis", 1, 1, "live_full_payload"),
            ("old-run", "tropical", "rfis", 1, 1, "live_full_payload"),  # counted: no run filter
            ("run-1", "tropical", "submittals", 1, 0, "live_full_payload"),  # excluded: stale
            ("run-1", "tropical", "submittals", 1, 1, "fixture_full_payload"),  # excluded: fixture
            ("run-1", "tropical", "submittals", 1, 1, "redacted_legacy_projection"),  # excluded
        ],
    )

    counts = orch.SourceRefreshOrchestrator(db_path=db_path)._current_live_full_payload_counts()

    assert counts["by_project"] == {"tropical": 3}
    assert counts["by_project_endpoint"] == {"tropical": {"rfis": 3}}


def test_freshness_taxonomy_classifies_each_endpoint(tmp_path: Any) -> None:
    db_path = _freshness_db(
        tmp_path,
        [
            ("r1", "tropical", "rfis", 1, 1, "live_full_payload"),
            ("r1", "tropical", "rfis", 1, 1, "live_full_payload"),
        ],
    )
    summary = {
        "endpoints": [
            # retrieved > 0 with current live rows present -> landed
            {
                "endpoint": "rfis",
                "scope": "tropical",
                "project_key": "tropical",
                "status": "success",
                "retrieved": 478,
                "sync_run_id": "r1",
            },
            # retrieved > 0 but no rows -> landing missing (fail closed)
            {
                "endpoint": "submittals",
                "scope": "tropical",
                "project_key": "tropical",
                "status": "success",
                "retrieved": 12,
                "sync_run_id": "r2",
            },
            # valid no-data / no-tool stage -> empty result (green)
            {
                "endpoint": "daily-log-weather",
                "scope": "tropical",
                "project_key": "tropical",
                "status": "success",
                "retrieved": 0,
                "sync_run_id": "r3",
            },
            # detail/full endpoint, list returned records, richer payload absent
            {
                "endpoint": "meeting-detail",
                "scope": "tropical",
                "project_key": "tropical",
                "status": "success",
                "retrieved": 4,
                "sync_run_id": "r4",
            },
            # explicit skip with reason -> green skip
            {"endpoint": "list-drawings", "scope": "n/a", "status": "skipped_tool_not_enabled"},
            # transport failure -> degraded, never green
            {
                "endpoint": "rfis",
                "scope": "pga-modern-garage",
                "project_key": "pga-modern-garage",
                "status": "transport_error_non_retryable",
                "retrieved": 0,
            },
        ]
    }
    fr = orch.SourceRefreshOrchestrator(db_path=db_path)._verify_procore_raw_payload_freshness(
        summary
    )
    counts = fr["counts_by_status"]
    assert counts["ok_payload_landed"] == 1
    assert counts["degraded_raw_payload_landing_missing"] == 1
    assert counts["ok_empty_result"] == 1
    assert counts["degraded_detail_payload_unavailable"] == 1
    assert counts["ok_skipped_with_reason"] == 1
    assert counts["degraded_external_blocked"] == 1
    # The gate fails closed only on raw-landing gaps (landing_missing + detail_unavailable).
    assert fr["ok"] is False
    assert fr["missing_fresh_raw_payload_count"] == 2
    # Transport failure is classified degraded, NOT a green skipped status.
    by_pair = {
        (r["project_key"], r["endpoint"]): r["freshness_status"]
        for r in fr["classified_endpoints"]
    }
    assert by_pair[("pga-modern-garage", "rfis")] == "degraded_external_blocked"
    assert by_pair[("tropical", "daily-log-weather")] == "ok_empty_result"
    # Receipt is counts-only: no payload values / secret-shaped strings.
    blob = json.dumps(fr)
    assert not any(tok in blob for tok in FORBIDDEN_RAW)
    assert fr["guardrails"]["emits_values"] is False


def test_freshness_all_landed_is_green_and_idempotent(tmp_path: Any) -> None:
    db_path = _freshness_db(
        tmp_path,
        [
            ("r1", "tropical", "rfis", 1, 1, "live_full_payload"),
            ("r1", "tropical", "submittals", 1, 1, "live_full_payload"),
        ],
    )
    summary = {
        "endpoints": [
            {
                "endpoint": "rfis",
                "scope": "tropical",
                "project_key": "tropical",
                "status": "success",
                "retrieved": 9,
                "sync_run_id": "r1",
            },
            {
                "endpoint": "submittals",
                "scope": "tropical",
                "project_key": "tropical",
                "status": "success",
                "retrieved": 3,
                "sync_run_id": "r1",
            },
        ]
    }
    orch_inst = orch.SourceRefreshOrchestrator(db_path=db_path)
    first = orch_inst._verify_procore_raw_payload_freshness(summary)
    second = orch_inst._verify_procore_raw_payload_freshness(summary)
    assert first["ok"] is True
    assert first["counts_by_status"]["ok_payload_landed"] == 2
    assert first["missing_fresh_raw_payload_count"] == 0
    # Re-running over unchanged landed rows is stable (no capture_run_id drift).
    assert first["counts_by_status"] == second["counts_by_status"]


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
    assert payload["email_calendar_projection_summary"]["status"] == "skipped"
    assert payload["email_calendar_projection_summary"]["reason"] == "procore_only"


def test_graph_only_skips_procore(patched: dict[str, Any]) -> None:
    _, payload = _run(["--graph-only", "--json"])
    assert payload["procore_sync_summary"]["status"] == "skipped"
    assert payload["procore_sync_summary"]["reason"] == "graph_only"
    assert payload["procore_projection_summary"]["status"] == "skipped"
    assert payload["procore_projection_summary"]["reason"] == "graph_only"


def test_graph_raw_ingestion_runs_before_email_calendar_projection(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator,
        "_graph_status",
        lambda self: {"token_type": "delegated"},
    )

    def _email_raw(self: Any, dry_run: bool) -> dict[str, Any]:
        order.append("email_raw")
        return {
            "status": "ok",
            "mode": "apply",
            "messages_seen": 1,
            "raw_emails_persisted": 1,
            "raw_threads_built": 1,
            "persisted": True,
        }

    def _calendar(self: Any, dry_run: bool) -> dict[str, Any]:
        order.append("calendar_raw")
        return {
            "status": "ok",
            "mode": "apply",
            "events_indexed": 1,
            "raw_events_persisted": 1,
            "persisted": True,
        }

    def _projection(**kw: Any) -> dict[str, Any]:
        order.append("v49_projection")
        return {
            "status": "ok",
            "mode": "apply",
            "run_id": "r1",
            "raw_rows_by_family": {"email_message": 1, "calendar_event": 1},
            "structured_rows_by_family": {"email_message": 1, "calendar_event": 1},
            "families_with_raw_rows": 2,
            "projection_coverage_status": "complete",
            "total_unmapped_business_fields": 0,
            "degraded_reason": [],
            "guardrails": {"external_writeback_performed": 0, "emits_values": False},
        }

    monkeypatch.setattr(orch.SourceRefreshOrchestrator, "_graph_email_raw", _email_raw)
    monkeypatch.setattr(orch.SourceRefreshOrchestrator, "_graph_calendar", _calendar)
    monkeypatch.setattr(orch, "run_email_calendar_projection_stage", _projection)

    _, payload = _run(["--graph-only", "--apply", "--confirm", "--json"])
    assert payload["graph_sync_summary"]["status"] == "ok"
    assert payload["email_calendar_projection_summary"]["status"] == "ok"
    assert order == ["email_raw", "calendar_raw", "v49_projection"]


def test_graph_degradation_does_not_mask_successful_procore(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator,
        "_graph_status",
        lambda self: {"token_type": "delegated"},
    )

    def _graph_boom(self: Any, dry_run: bool) -> dict[str, Any]:
        raise RuntimeError("graph raw failed")

    monkeypatch.setattr(orch.SourceRefreshOrchestrator, "_graph_email_raw", _graph_boom)
    _, payload = _run(["--all", "--apply", "--confirm", "--json"])
    assert payload["status"] == "degraded"
    assert payload["procore_sync_summary"]["status"] == "ok"
    assert payload["procore_projection_summary"]["status"] == "ok"
    assert payload["graph_sync_summary"]["status"] == "degraded"


def test_contract_bug_endpoint_degrades_run(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)

    def fake_run_live_sync(**kw: Any) -> dict[str, Any]:
        patched["run_live_sync"].append(kw)
        if kw.get("endpoint") == "punch-items":
            return {
                "endpoint_id": "punch-items",
                "state": "transport_error",
                "status": "error",
                "reason_codes": ["transport_error:400"],
                "redacted_errors": [{"code": "http_error", "status": 400}],
                "sqlite_upserted_count": 0,
                "retrieved_count": 0,
            }
        return {
            "endpoint_id": kw.get("endpoint"),
            "state": "success",
            "status": "success",
            "reason_codes": [],
            "redacted_errors": [],
            "sqlite_upserted_count": 3,
            "retrieved_count": 3,
        }

    monkeypatch.setattr(orch, "run_live_sync", fake_run_live_sync)
    # --procore-only isolates the Procore stage (Graph has no token in this fixture
    # and would otherwise degrade the run + own the top-level next_operator_action).
    code, payload = _run(["--procore-only", "--apply", "--confirm", "--json"])
    assert code == 1  # degraded run -> nonzero
    assert payload["status"] == "degraded"
    procore = payload["procore_sync_summary"]
    assert procore["status"] == "degraded"
    assert procore["endpoint_summary"]["contract_bug_failures"] >= 1
    # punch-items is per-project; one contract bug per pilot project
    bug_rows = [
        e for e in procore["endpoints"] if e["status"] == "contract_bug_missing_required_param"
    ]
    assert bug_rows and all(e["endpoint"] == "punch-items" for e in bug_rows)
    assert "contract regression" in procore["next_operator_action"]
    assert "contract regression" in payload["next_operator_action"]


def test_drawings_classified_skipped_not_failure(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    # --procore-only: Graph (no token here) must not degrade this Procore assertion.
    _, payload = _run(["--procore-only", "--apply", "--confirm", "--json"])
    procore = payload["procore_sync_summary"]
    drawings = [e for e in procore["endpoints"] if e["endpoint"] == "list-drawings"]
    assert drawings and drawings[0]["status"] == "skipped_tool_not_enabled"
    # an all-success run with only the drawings skip is NOT degraded
    assert procore["status"] == "ok"
    assert payload["status"] == "ok"


def test_apply_receipt_has_no_token_shaped_values(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orch, "live_env_active", lambda: True)
    result = runner.invoke(app, CMD + ["--all", "--apply", "--confirm", "--json"])
    for token in FORBIDDEN_RAW:
        assert token not in result.output
    payload = json.loads(result.stdout)
    assert payload["procore_sync_summary"]["persistence_path"] == "procore_live"
    assert payload["procore_sync_summary"]["tables_written"] == [
        "procore_live_records",
        "procore_live_sync_runs",
        "procore_live_sync_watermarks",
    ]


def test_v2_packet_generated_after_refresh(patched: dict[str, Any]) -> None:
    _, payload = _run(["--all", "--date", "2026-06-07", "--json"])
    db = payload["daily_brief_v2_summary"]
    assert db["packet_version"] == "DailyBriefHandoffPacketV2"
    assert db["brief_date"] == "2026-06-07"


def test_no_raw_content_in_output(patched: dict[str, Any]) -> None:
    result = runner.invoke(app, CMD + ["--all", "--json"])
    for token in FORBIDDEN_RAW:
        assert token not in result.output


def test_graph_and_projection_summaries_are_raw_free(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "SECRET_BODY_SENTINEL https://teams.microsoft.com/l/meetup user@example.com"
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator,
        "_graph_status",
        lambda self: {"token_type": "delegated"},
    )
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator,
        "_graph_email_raw",
        lambda self, dry_run: {
            "status": "ok",
            "mode": "apply",
            "messages_seen": 1,
            "raw_emails_persisted": 1,
            "persisted": True,
        },
    )
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator,
        "_graph_calendar",
        lambda self, dry_run: {
            "status": "ok",
            "mode": "apply",
            "events_indexed": 1,
            "raw_events_persisted": 1,
            "persisted": True,
        },
    )
    monkeypatch.setattr(
        orch,
        "run_email_calendar_projection_stage",
        lambda **kw: {
            "status": "ok",
            "mode": "apply",
            "run_id": "r1",
            "raw_rows_by_family": {"email_message": 1},
            "structured_rows_by_family": {"email_message": 1},
            "families_with_raw_rows": 1,
            "projection_coverage_status": "complete",
            "total_unmapped_business_fields": 0,
            "degraded_reason": [],
            "guardrails": {"external_writeback_performed": 0, "emits_values": False},
            "not_emitted_raw_value": secret,
        },
    )
    result = runner.invoke(app, CMD + ["--graph-only", "--apply", "--confirm", "--json"])
    assert secret not in result.output
    payload = json.loads(result.stdout)
    blob = json.dumps(
        [payload["graph_sync_summary"], payload["email_calendar_projection_summary"]]
    )
    for token in ("SECRET_BODY_SENTINEL", "teams.microsoft.com", "user@example.com"):
        assert token not in blob


class _DryRunMailClient:
    def __init__(self) -> None:
        self.body_fetches = 0

    def get_me(self) -> dict[str, Any]:
        return {"mail": "owner@example.com"}

    def list_messages(self, **kw: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "m1",
                "conversationId": "c1",
                "subject": "Body fetch dry run",
                "bodyPreview": "preview",
                "from": {"emailAddress": {"address": "sender@example.com"}},
                "receivedDateTime": "2026-06-01T00:00:00Z",
            }
        ]

    def get_message_body(self, message_id: str) -> dict[str, Any]:
        self.body_fetches += 1
        raise AssertionError("dry-run must not fetch full message bodies")


class _DryRunCalendarClient:
    def __init__(self) -> None:
        self.event_fetches = 0

    def get_me(self) -> dict[str, Any]:
        return {"mail": "owner@example.com"}

    def list_calendar_view(self, **kw: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "e1",
                "subject": "Full event dry run",
                "start": {"dateTime": "2026-06-01T10:00:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-06-01T10:30:00", "timeZone": "UTC"},
            }
        ]

    def get_event(self, event_id: str) -> dict[str, Any]:
        self.event_fetches += 1
        raise AssertionError("dry-run must not fetch full calendar events")


def test_dry_run_raw_indexers_do_not_fetch_full_bodies(tmp_path: Path) -> None:
    store = ConstructionStore(db_path=str(tmp_path / "dry.sqlite"))
    store.upsert_email_source_location(
        source_id="inbox",
        mailbox_owner_hash="owner",
        folder_id="inbox",
        folder_display_name="Inbox",
        folder_role="included",
        include_in_sync=True,
    )
    mail = _DryRunMailClient()
    email_result = EmailMessageIndexer(mail, store).index(
        dry_run=True, include_raw_content=True
    )
    assert email_result.raw_emails_persisted == 0
    assert mail.body_fetches == 0

    calendar = _DryRunCalendarClient()
    cal_result = CalendarEventIndexer(calendar, store).index(
        source_id="primary",
        dry_run=True,
        include_raw_content=True,
        max_items=1,
    )
    assert cal_result.raw_events_persisted == 1
    assert calendar.event_fetches == 0
    conn = sqlite3.connect(store._db_path)
    assert conn.execute("SELECT COUNT(*) FROM email_message_raw_content").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_raw_content").fetchone()[0] == 0


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
