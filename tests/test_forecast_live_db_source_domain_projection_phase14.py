"""Phase 14 — controlled live DB source-domain projection (first gated live write).

Exercises the gated live-write workflow against a SYNTHETIC "live" DB (a migrated temp DB whose path
is monkeypatched to be treated as the live/default DB). Covers preflight refusals, backup + WAL gate,
temp projection + expected-count gate, the tropical-only transactional replace (preserving
non-tropical rows), rollback on in-transaction failure, post-write certification, the optional guarded
proof, and CLI rc 0/1/3. Everything runs under ``tmp_path``; the real live DB is never touched.

build_fixture / _wj / _wjson MIRROR the Phase 11/12/13 tests (duplicated, not imported).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review.workflows import live_db_certification as certmod  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    live_db_source_domain_projection as proj,
)
from construction_financial_review.workflows.live_db_source_domain_projection import (  # noqa: E402
    DECISION_CERTIFIED,
    LiveDbSourceDomainProjectionError,
    run_controlled_live_db_source_domain_projection,
)

BCK = "0000.03-01-025.MAT"
PROCORE_DIRNAME = "cost_forecast_agent_db_json_export_tropical_20260614_080344"
STAMP = "20260101_000000"
REQUIRED_TABLES = (
    "forecast_budget_details",
    "forecast_cost_entries",
    "forecast_monthly_actuals_by_budget_code",
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for var in (
        "HB_FORECAST_DB_BACKED_READS",
        "HB_FORECAST_DB_PATH",
        "CFR_CONTEXT_DATA_ROOT",
        "CFR_CONTEXT_OUT_DIR",
        "CFR_CONTEXT_STAMP",
        "CFR_RUN_LINEAGE_STATE",
    ):
        monkeypatch.delenv(var, raising=False)


def _source_package(root: Path) -> Path:
    return build_fixture(root) / "twn_cost_forecast_json_package"


def _same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def _checkpoint(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _build_live_db(path: Path, source_package: Path | None = None) -> None:
    """Synthetic 'live' DB: migrate (+ optionally project), then TRUNCATE-checkpoint (WAL size 0)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(path)).apply()
    if source_package is not None:
        rec = dbeng.project_source_domain(
            source_package=source_package, project_key="tropical", db_path=path, apply=True
        )
        assert rec["ok"] is True
    _checkpoint(path)


def _seed_row(path: Path, *, project_key: str) -> None:
    """Insert one minimal-valid forecast_budget_details row for a given project_key; checkpoint."""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "INSERT INTO forecast_budget_details "
            "(project_key, budget_code_key, source_package, raw_json, created_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                project_key,
                f"{project_key}.code",
                "twn_cost_forecast_json_package",
                json.dumps({"k": project_key}),
                "2026-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    _checkpoint(path)


def _flag_live(monkeypatch, live_path: Path) -> None:
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, live_path))


def _content_sig(p: Path) -> tuple[int, str]:
    b = Path(p).read_bytes()
    return len(b), hashlib.sha256(b).hexdigest()


def _tropical_total(path: Path) -> int:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return sum(
            conn.execute(f"SELECT COUNT(*) FROM {t} WHERE project_key='tropical'").fetchone()[0]
            for t in REQUIRED_TABLES
        )
    finally:
        conn.close()


# --- 1-8. preflight / gate refusals ---------------------------------------------------


def test_refuses_without_allow_live_db_write(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="allow_live_db_write"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, live_db_path=live
        )


def test_refuses_non_live_db(tmp_path):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)  # real is_live_db_path -> False
    with pytest.raises(LiveDbSourceDomainProjectionError, match="not the live/default DB"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )


def test_refuses_missing_source(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="source_package not found"):
        run_controlled_live_db_source_domain_projection(
            source_package=tmp_path / "src" / "twn_cost_forecast_json_package",
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )


def test_refuses_unsafe_work_root(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    fake_live_root = tmp_path / "fake_live_root"
    monkeypatch.setattr(proj, "_LIVE_ROOT", fake_live_root)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="live forecast root"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=fake_live_root / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )


def test_refuses_missing_live_db(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"  # never built
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="live DB not found"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )


def test_refuses_schema_below_59(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    live.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(live))
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)"
    )
    conn.execute("INSERT INTO schema_migrations VALUES (1, 'v1', '2025-01-01')")
    for t in REQUIRED_TABLES:
        conn.execute(f"CREATE TABLE {t} (project_key TEXT, raw_json TEXT)")
    conn.commit()
    conn.close()
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="schema version"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )


def test_refuses_missing_required_tables(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    live.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(live))
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)"
    )
    conn.execute("INSERT INTO schema_migrations VALUES (59, 'v59', '2025-01-01')")
    conn.commit()
    conn.close()
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="missing one or more required"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )


def test_refuses_nonzero_wal(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    real_prov = certmod._file_provenance
    monkeypatch.setattr(
        certmod,
        "_file_provenance",
        lambda p: {**real_prov(p), "wal_exists": True, "wal_size_bytes": 4096},
    )
    with pytest.raises(LiveDbSourceDomainProjectionError, match="nonzero WAL"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )
    assert not (tmp_path / "work" / "backups").exists()  # no backup created before the gate


# --- 9-22. backup, temp projection, transactional write, certification ----------------


def _run_success(tmp_path, monkeypatch, **kwargs) -> dict:
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)  # empty schema_only live DB
    _flag_live(monkeypatch, live)
    return run_controlled_live_db_source_domain_projection(
        source_package=sp,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        live_db_path=live,
        allow_live_db_write=True,
        **kwargs,
    )


def test_creates_and_verifies_backup(tmp_path, monkeypatch):
    report = _run_success(tmp_path, monkeypatch)
    b = report["backup"]
    assert Path(b["path"]).is_file()
    assert b["verified_readable"] is True and b["schema_version"] >= 59  # synthetic temp DB at migrator head
    assert b["size_bytes"] > 0 and len(b["sha256"]) == 64


def test_backup_root_param_durable(tmp_path, monkeypatch):
    durable = tmp_path / "durable"
    report = _run_success(tmp_path, monkeypatch, backup_root=durable)
    b = report["backup"]
    expected = durable / proj._backup_name(STAMP)
    assert Path(b["path"]) == expected and expected.is_file()
    assert b["backup_root"] == str(durable)
    # The durable root replaces the ephemeral work_root/backups fallback (not both).
    assert not (tmp_path / "work" / "backups").exists()


def test_backup_root_under_live_root_refused(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    fake_live_root = tmp_path / "fake_live_root"
    monkeypatch.setattr(proj, "_LIVE_ROOT", fake_live_root)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="backup_root is at/under"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
            backup_root=fake_live_root / "backups",
        )
    assert not (fake_live_root / "backups").exists()  # refused before any backup


def test_builds_temp_and_counts(tmp_path, monkeypatch):
    report = _run_success(tmp_path, monkeypatch)
    assert Path(report["temp_db"]["path"]).is_file()
    assert report["temp_db"]["counts"] == {
        "forecast_budget_details": 1,
        "forecast_cost_entries": 2,
        "forecast_monthly_actuals_by_budget_code": 2,
    }


def test_expected_counts_match(tmp_path, monkeypatch):
    report = _run_success(
        tmp_path,
        monkeypatch,
        expected_counts={
            "forecast_budget_details": 1,
            "forecast_cost_entries": 2,
            "forecast_monthly_actuals_by_budget_code": 2,
        },
    )
    assert report["decision"] == DECISION_CERTIFIED


def test_expected_counts_mismatch_fails_before_write(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    before = _content_sig(live)
    with pytest.raises(
        LiveDbSourceDomainProjectionError, match="expected temp-projection row counts"
    ):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
            expected_counts={"forecast_budget_details": 999},
        )
    assert _content_sig(live) == before  # live untouched
    assert not (tmp_path / "work" / "backups").exists()  # count gate is before backup


def test_transaction_copies_only_three_tables(tmp_path, monkeypatch):
    report = _run_success(tmp_path, monkeypatch)
    assert set(report["write_result"]["by_table"]) == set(REQUIRED_TABLES)
    assert report["write_result"]["transaction_committed"] is True


def test_preserves_non_tropical_rows(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _seed_row(live, project_key="other")  # non-tropical row must survive
    _flag_live(monkeypatch, live)
    run_controlled_live_db_source_domain_projection(
        source_package=sp,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        live_db_path=live,
        allow_live_db_write=True,
    )
    conn = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    try:
        other = conn.execute(
            "SELECT COUNT(*) FROM forecast_budget_details WHERE project_key='other'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert other == 1


def test_refuses_existing_tropical_without_replace(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _seed_row(live, project_key="tropical")
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="already has .* tropical"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )


def test_allows_replace_existing_tropical(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _seed_row(live, project_key="tropical")
    _flag_live(monkeypatch, live)
    report = run_controlled_live_db_source_domain_projection(
        source_package=sp,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        live_db_path=live,
        allow_live_db_write=True,
        allow_replace_existing=True,
    )
    assert report["decision"] == DECISION_CERTIFIED
    assert report["replaced_existing_tropical_rows"] == 1


def test_rolls_back_on_insert_failure(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _seed_row(live, project_key="other")
    _flag_live(monkeypatch, live)
    before = _content_sig(live)

    def _boom(conn, table, project_key, expected):
        raise proj.LiveDbSourceDomainProjectionError(f"forced failure on {table}")

    monkeypatch.setattr(proj, "_verify_inserted", _boom)
    with pytest.raises(LiveDbSourceDomainProjectionError, match="forced failure"):
        run_controlled_live_db_source_domain_projection(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
            allow_live_db_write=True,
        )
    # transaction rolled back: live content unchanged, non-tropical row intact, backup still present
    assert _content_sig(live) == before
    assert _tropical_total(live) == 0
    assert (tmp_path / "work" / "backups" / proj._backup_name(STAMP)).is_file()


def test_post_write_audit_and_certification(tmp_path, monkeypatch):
    report = _run_success(tmp_path, monkeypatch)
    assert report["decision"] == DECISION_CERTIFIED
    assert report["status"] == "ready"
    assert report["post_write_audit"]["source_domain"]["tropical_total"] == 5
    assert report["post_write_certification"]["decision"] == "certified_match"
    for t in REQUIRED_TABLES:
        assert report["post_write_certification"]["tables"][t]["match"] is True


def test_report_deterministic_and_blocks(tmp_path, monkeypatch):
    report = _run_success(tmp_path, monkeypatch)
    raw = Path(report["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"
    for block in (
        "backup",
        "pre_write_audit",
        "write_result",
        "post_write_certification",
        "safety",
    ):
        assert block in loaded
    assert loaded["safety"] == {
        "live_db_written": True,
        "live_db_migrated": False,
        "live_db_projected_directly": False,
        "projected_via_temp_db": True,
        "live_root_written": False,
        "production_defaults_changed": False,
        "final_integrated_csv_generated": False,
        "true_live_execution_used": False,
    }


# --- 23. optional guarded operator proof ----------------------------------------------


def test_guarded_operator_check(tmp_path, monkeypatch):
    report = _run_success(tmp_path, monkeypatch, run_guarded_operator_check=True)
    gc = report["guarded_operator_check"]
    assert gc is not None
    assert gc["status"] == "ready"
    assert gc["decision"] == "approved_for_guarded_db_context_analysis_use"
    assert gc["live_db"]["used_for_execution"] is False
    assert gc["live_db"]["equivalent_to_temp_db"] is True


# --- 24-26. CLI -----------------------------------------------------------------------


def test_cli_success_rc0(tmp_path, monkeypatch, capsys):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    rc = cli.main(
        [
            "live-db-source-domain-project",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--live-db-path",
            str(live),
            "--allow-live-db-write",
            "--expect-budget-details",
            "1",
            "--expect-cost-entries",
            "2",
            "--expect-monthly",
            "2",
        ]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == DECISION_CERTIFIED


def test_cli_not_ready_rc1(tmp_path, monkeypatch, capsys):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    # Force post-write certification to report non-match -> not_ready / rc 1 (write still happened).
    real_cert = certmod.run_live_db_readonly_certification
    monkeypatch.setattr(
        certmod,
        "run_live_db_readonly_certification",
        lambda **kw: {**real_cert(**kw), "decision": "stale_or_mismatch"},
    )
    rc = cli.main(
        [
            "live-db-source-domain-project",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--live-db-path",
            str(live),
            "--allow-live-db-write",
        ]
    )
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "not_ready"


def test_cli_refusal_rc3(tmp_path, monkeypatch, capsys):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live)
    _flag_live(monkeypatch, live)
    rc = cli.main(
        [
            "live-db-source-domain-project",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--live-db-path",
            str(live),
        ]
    )  # no --allow-live-db-write
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_existing_cli_commands_still_route():
    parser = cli.build_parser()
    for cmd in ("run-context", "run-analysis"):
        assert parser.parse_args([cmd, "--project", "tropical"]).command == cmd
    lsp = parser.parse_args(
        [
            "live-db-source-domain-project",
            "--project",
            "tropical",
            "--source-package",
            "/x",
            "--work-root",
            "/y",
            "--context-stamp",
            "s",
            "--allow-live-db-write",
            "--allow-replace-existing",
            "--run-guarded-operator-check",
            "--expect-budget-details",
            "127",
            "--expect-cost-entries",
            "6324",
            "--expect-monthly",
            "1081",
        ]
    )
    assert lsp.command == "live-db-source-domain-project"
    assert lsp.allow_live_db_write is True and lsp.allow_replace_existing is True
    assert lsp.run_guarded_operator_check is True
    assert lsp.expect_budget_details == 127 and lsp.expect_cost_entries == 6324
    assert lsp.expect_monthly == 1081
    # Phase 13 commands unchanged
    assert (
        parser.parse_args(
            [
                "live-db-readonly-certification",
                "--project",
                "tropical",
                "--source-package",
                "/x",
                "--work-root",
                "/y",
                "--context-stamp",
                "s",
            ]
        ).command
        == "live-db-readonly-certification"
    )


# --- duplicated synthetic source fixture (mirrors Phase 11/12/13 build_fixture) --------


def _wj(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _wjson(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def build_fixture(root: Path) -> Path:
    """Minimal-valid synthetic source packages: one budget code through every dependency."""
    twn = root / "twn_cost_forecast_json_package"
    owner = root / "owner_pay_app_json_package"
    proc = root / PROCORE_DIRNAME
    _wj(
        twn / "data" / "budget_details.jsonl",
        [
            {
                "source_sheet": "BudgetDetails",
                "source_row": 2,
                "budget_code_key": BCK,
                "extra": "0000",
                "sub_job": {"raw": "0000 - X", "code": "0000", "description": "X"},
                "cost_code": "03-01-025",
                "cost_code_tiers": {
                    "tier_1": {"raw": "03 - EST", "code": "03", "description": "EST"},
                    "tier_2": {"raw": "03-01 - GC", "code": "03-01", "description": "GC"},
                    "tier_3": {"raw": "03-01-025 - PCE", "code": "03-01-025", "description": "PCE"},
                },
                "category": "MAT",
                "cost_type": {"raw": "MAT - Materials", "code": "MAT", "description": "Materials"},
                "budget_code_description": "X.PCE.Materials",
                "amounts": {
                    "original_budget_amount": 0.0,
                    "budget_modifications": 1000.0,
                    "approved_cos": 0.0,
                    "revised_budget": 1000.0,
                    "pending_budget_changes": 0.0,
                    "projected_budget": 1000.0,
                    "committed_costs": 0.0,
                    "commitment_invoiced": 0.0,
                    "erp_direct_costs": 500.0,
                    "erp_job_to_date_costs": 500.0,
                    "pending_cost_changes": 0.0,
                    "projected_costs": 500.0,
                    "estimated_cost_at_completion": 500.0,
                    "forecast_to_complete": 0.0,
                    "projected_over_under": 500.0,
                    "costentries_total_amount": 500.0,
                    "costentries_entry_count": 2,
                },
                "notes": None,
                "costentries_match_status": "Matched",
            }
        ],
    )
    _wj(
        twn / "data" / "cost_entries.jsonl",
        [
            {
                "source_sheet": "CostEntries",
                "source_row": 2,
                "job": "23-435-01",
                "job_description": "TWN",
                "job2": "23-435-01",
                "extra": "0000",
                "cost_code": "03-01-025",
                "category": "MAT",
                "tran_type": "AP cost",
                "accounting_date": "2024-06-30",
                "accounting_month": "2024-06",
                "amount": 300.0,
                "description": None,
                "application_of_origin": "AP",
                "budget_code_key": BCK,
            },
            {
                "source_sheet": "CostEntries",
                "source_row": 3,
                "job": "23-435-01",
                "job_description": "TWN",
                "job2": "23-435-01",
                "extra": "0000",
                "cost_code": "03-01-025",
                "category": "MAT",
                "tran_type": "AP cost",
                "accounting_date": "2026-06-05",
                "accounting_month": "2026-06",
                "amount": 200.0,
                "description": None,
                "application_of_origin": "AP",
                "budget_code_key": BCK,
            },
        ],
    )
    _wj(
        twn / "data" / "monthly_actuals_by_budget_code.jsonl",
        [
            {
                "budget_code_key": BCK,
                "month": "2024-06",
                "type": "actual",
                "amount": 300.0,
                "entry_count": 1,
                "job": "23-435-01",
                "extra": "0000",
                "cost_code": "03-01-025",
                "category": "MAT",
                "first_accounting_date": "2024-06-30",
                "last_accounting_date": "2024-06-30",
                "source": "CostEntries",
            },
            {
                "budget_code_key": BCK,
                "month": "2026-06",
                "type": "actual",
                "amount": 200.0,
                "entry_count": 1,
                "job": "23-435-01",
                "extra": "0000",
                "cost_code": "03-01-025",
                "category": "MAT",
                "first_accounting_date": "2026-06-05",
                "last_accounting_date": "2026-06-05",
                "source": "CostEntries",
            },
        ],
    )
    _wjson(twn / "validation_report.json", {"status": "ok", "checks": []})
    _wjson(twn / "manifest.json", {"package_name": "twn_cost_forecast_json_package"})
    _wj(
        owner / "owner_pay_app_line_items.jsonl",
        [
            {
                "source_workbook": "TWN-Owner-Pay-Apps.xlsx",
                "source_sheet": "App 1",
                "source_row": 5,
                "sheet_index": 0,
                "application_no": 1,
                "application_date": "2026-05-31",
                "period_to": "2026-05-31",
                "contractor_project_no": "23-435-01",
                "row_type": "line_item",
                "item": "1",
                "owner_sov_code": "03-01-025",
                "cost_code": "03-01-025",
                "description_of_work": "GC",
                "candidate_budget_code_keys": [BCK],
                "validation_flags": [],
                "scheduled_value": 1000.0,
                "current_value": 1000.0,
                "work_completed": {
                    "from_previous_application": 0.0,
                    "this_period": 500.0,
                    "materials_presently_stored": 0.0,
                    "total_completed_and_stored_to_date": 500.0,
                    "percent_complete": 50.0,
                    "balance_to_finish": 500.0,
                },
                "retainage": {"retainage_current_or_reduced": 50.0},
            }
        ],
    )
    _wj(
        owner / "owner_pay_app_totals.jsonl",
        [
            {
                "source_workbook": "TWN-Owner-Pay-Apps.xlsx",
                "source_sheet": "App 1",
                "source_row": 20,
                "sheet_index": 0,
                "application_no": 1,
                "period_to": "2026-05-31",
                "row_type": "grand_total",
                "description_of_work": "GRAND TOTAL",
                "cost_code": None,
                "scheduled_value": 1000.0,
                "current_value": 1000.0,
                "work_completed": {
                    "this_period": 500.0,
                    "total_completed_and_stored_to_date": 500.0,
                },
                "retainage": {"retainage_current_or_reduced": 50.0},
            }
        ],
    )
    _wjson(owner / "owner_pay_app_validation_report.json", {"status": "ok"})
    _wjson(owner / "owner_pay_app_sheet_manifest.json", {"sheets": []})
    _wj(
        proc / "procore_subcontractor_payment_app_headers.jsonl",
        [
            {
                "record_key": "h1",
                "period_end": "2026-05-31",
                "billing_date": "2026-05-31",
                "submitted_at": "2026-05-31",
                "updated_at_utc": "2026-05-31T00:00:00Z",
            }
        ],
    )
    _wj(
        proc / "procore_subcontractor_payment_app_line_items.jsonl",
        [
            {
                "invoice_item_key": "li1",
                "wbs_flat_code": BCK,
                "period_end": "2026-05-31",
                "vendor_entity_key": "v1",
                "commitment_id": "c1",
                "scheduled_value": 1000.0,
                "work_completed_this_period": 500.0,
                "materials_presently_stored": 0.0,
                "total_completed_and_stored_to_date": 500.0,
                "retainage_held": 50.0,
                "subcontractor_claimed_amount": 500.0,
                "invoice_record_key": "h1",
            }
        ],
    )
    _wj(
        proc / "procore_latest_subcontractor_invoice_by_vendor_cost_code.jsonl",
        [
            {
                "source_invoice_item_key": "li1",
                "wbs_flat_code": BCK,
                "vendor_entity_key": "v1",
                "commitment_id": "c1",
                "latest_period_end": "2026-05-31",
                "latest_scheduled_value": 1000.0,
                "latest_work_completed_this_period": 500.0,
                "latest_materials_presently_stored": 0.0,
                "latest_total_completed_and_stored_to_date": 500.0,
                "latest_retainage_held": 50.0,
            }
        ],
    )
    _wj(
        proc / "procore_commitments.jsonl",
        [
            {
                "contract_id": "c1",
                "record_key": "c1",
                "number": "SC-001",
                "status": "Approved",
                "contract_family": "03-01",
                "contract_type": "Subcontract",
                "executed": True,
                "vendor_entity_key": "v1",
                "company_entity_key": "co1",
                "grand_total": 1000.0,
                "original_contract_sum": 1000.0,
                "revised_contract_sum": 1000.0,
                "approved_change_orders_amount": 0.0,
                "pending_change_orders_amount": 0.0,
                "retainage_percent": 5.0,
                "contract_date": "2026-01-01",
                "start_date": "2026-01-01",
                "completion_date": "2026-12-31",
                "updated_at_utc": "2026-05-31T00:00:00Z",
            }
        ],
    )
    _wj(
        proc / "procore_payapp_amount_facts_through_may_2026.jsonl",
        [{"period_end": "2026-05-31", "period_start": "2026-05-01"}],
    )
    _wjson(
        proc / "forecast_mapping_template.json",
        [
            {
                "procore_wbs_flat_code": BCK,
                "procore_commitment_id": "c1",
                "procore_vendor_entity_key": "v1",
            }
        ],
    )
    _wjson(proc / "procore_db_export_validation_report.json", {"status": "ok"})
    return root
