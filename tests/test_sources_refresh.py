"""Tests for the unified `construction-agent refresh-sources` orchestration command.

The orchestrator imports the heavy Procore/Graph/second-brain surfaces at its own
module namespace, so we patch them there for deterministic, network-free runs. Auth
and external readers are stubbed; the real ``SQLiteMigrator`` is used only for the
auto-migrate test.
"""

from __future__ import annotations

import json
import sqlite3
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
    calls: dict[str, Any] = {"run_live_sync": [], "calendar": 0, "files": 0}

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
    monkeypatch.setattr(
        orch.SourceRefreshOrchestrator,
        "_raw_full_payload_counts_for_current_sync",
        lambda self, procore_summary: {
            "sync_run_ids_checked": [
                e["sync_run_id"] for e in procore_summary.get("endpoints", []) if e.get("sync_run_id")
            ],
            "by_project": {
                p: sum(
                    int(e.get("raw_payload_rows_written", 0) or 0)
                    for e in procore_summary.get("endpoints", [])
                    if e.get("scope") == p and e.get("status") == "success"
                )
                for p in {e.get("scope") for e in procore_summary.get("endpoints", [])}
                if p and p != "company"
            },
            "by_project_endpoint": {
                p: {
                    e["endpoint"]: int(e.get("raw_payload_rows_written", 0) or 0)
                    for e in procore_summary.get("endpoints", [])
                    if e.get("scope") == p and e.get("status") == "success"
                }
                for p in {e.get("scope") for e in procore_summary.get("endpoints", [])}
                if p and p != "company"
            },
        },
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
    assert graph["families"]["calendar_event_index"]["status"] == "blocked_auth_not_ready"
    assert graph["families"]["files"]["status"] == "blocked_auth_not_ready"
    # live Graph indexers were never invoked
    assert patched["calendar"] == 0 and patched["files"] == 0
    assert payload["status"] == "degraded"


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
    assert proj["projection_audit"]["ok"] is True
    assert proj["projection_audit"]["unknown_business_field_paths"] == 0
    assert proj["projection_audit"]["runtime_plan_schema_mismatches"] == 0


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
        "_raw_full_payload_counts_for_current_sync",
        lambda self, procore_summary: {
            "sync_run_ids_checked": ["sync-1"],
            "by_project": {},
            "by_project_endpoint": {},
        },
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


def test_raw_payload_freshness_counts_only_current_live_full_rows(tmp_path: Any) -> None:
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
            "INSERT INTO procore_endpoint_raw_payloads VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("run-1", "tropical", "rfis", 1, 1, "live_full_payload"),
                ("run-1", "tropical", "rfis", 1, 1, "live_full_payload"),
                ("run-1", "tropical", "submittals", 1, 0, "live_full_payload"),
                ("run-1", "tropical", "submittals", 1, 1, "fixture_full_payload"),
                ("old-run", "tropical", "rfis", 1, 1, "live_full_payload"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    counts = orch.SourceRefreshOrchestrator(db_path=db_path)._raw_full_payload_counts_for_current_sync(
        {"endpoints": [{"sync_run_id": "run-1"}]}
    )

    assert counts["sync_run_ids_checked"] == ["run-1"]
    assert counts["by_project"] == {"tropical": 2}
    assert counts["by_project_endpoint"] == {"tropical": {"rfis": 2}}


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
