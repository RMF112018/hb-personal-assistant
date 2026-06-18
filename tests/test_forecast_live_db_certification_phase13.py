"""Phase 13 — live DB provenance audit, read-only certification & guarded live-DB opt-in.

Strictly read-only audit + certification of a SYNTHETIC "live" DB (a temp DB whose path is
monkeypatched to be treated as the live/default DB), plus the certified-equivalence guarded
operator-run opt-in. Audit/certification tests open the synthetic live DB read-only only; the
certified-equivalence guarded run executes against a FRESH temp DB and never threads the live DB
into Phase 9. Everything runs under ``tmp_path``; the real live DB is never touched.

build_fixture / _wj / _wjson MIRROR the Phase 11/12 tests (duplicated, not imported).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

# hb_assistant is imported lazily by the audit/cert + projection paths; tests monkeypatch the live-DB
# check and drive real migration + projection into temp DBs.
from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    guarded_db_operator_run as guarded,
)
from construction_financial_review.workflows import (  # noqa: E402
    live_db_certification as certmod,
)
from construction_financial_review.workflows.guarded_db_operator_run import (  # noqa: E402
    GuardedDbOperatorRunError,
    run_guarded_db_operator_run,
)
from construction_financial_review.workflows.live_db_certification import (  # noqa: E402
    CERT_MATCH,
    CERT_REPORT_SCHEMA_VERSION,
    LiveDbCertificationError,
    run_live_db_provenance_audit,
    run_live_db_readonly_certification,
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
    """Fully merge the WAL into the main file so read-only reads can't drift its content/mtime."""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _build_live_db(path: Path, source_package: Path) -> None:
    """Migrate + project a temp DB to act as the synthetic 'live' DB (built BEFORE monkeypatching)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(path)).apply()
    rec = dbeng.project_source_domain(
        source_package=source_package, project_key="tropical", db_path=path, apply=True
    )
    assert rec["ok"] is True
    _checkpoint(path)


def _build_schema_only_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(path)).apply()
    _checkpoint(path)


def _flag_live(monkeypatch, live_path: Path) -> None:
    """Treat ``live_path`` (and only it) as the live/default DB for audit/cert/guarded checks."""
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, live_path))


def _content_sig(p: Path) -> tuple[int, str]:
    """Content signature of the MAIN DB file (size + sha256) — the true 'not written' invariant.

    mtime/-wal/-shm metadata can change from read-only opens (WAL); only main-file CONTENT matters.
    """
    b = Path(p).read_bytes()
    return len(b), hashlib.sha256(b).hexdigest()


# --- 1-9. provenance audit ------------------------------------------------------------


def test_audit_reads_synthetic_live_readonly(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    report = run_live_db_provenance_audit(live_db_path=live, project_key="tropical")
    assert report["decision"] == "populated_tropical"
    assert report["schema"]["schema_version"] == 59
    assert report["schema"]["required_tables_present"] == dict.fromkeys(REQUIRED_TABLES, True)
    assert report["safety"]["read_only"] is True


def test_audit_reports_migration_rows(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    report = run_live_db_provenance_audit(live_db_path=live, project_key="tropical")
    migs = report["schema"]["migrations"]
    assert migs and {"version", "name", "applied_at"} <= set(migs[0])
    assert max(m["version"] for m in migs) == 59


def test_audit_reports_counts_by_project_key(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    report = run_live_db_provenance_audit(live_db_path=live, project_key="tropical")
    sd = report["source_domain"]
    assert sd["distinct_project_keys"] == ["tropical"]
    assert sd["tropical_total"] > 0
    for t in REQUIRED_TABLES:
        assert sd["by_table"][t]["tropical_rows"] > 0


def test_audit_schema_only(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _build_schema_only_db(live)
    _flag_live(monkeypatch, live)
    report = run_live_db_provenance_audit(live_db_path=live, project_key="tropical")
    assert report["decision"] == "schema_only"
    assert report["source_domain"]["tropical_total"] == 0
    assert report["schema"]["required_tables_present"] == dict.fromkeys(REQUIRED_TABLES, True)


def test_audit_refuses_missing_db(tmp_path):
    with pytest.raises(LiveDbCertificationError, match="live DB not found"):
        run_live_db_provenance_audit(live_db_path=tmp_path / "nope.sqlite", project_key="tropical")


def test_audit_refuses_non_live_db(tmp_path):
    live = tmp_path / "live" / "hb.sqlite"
    _build_schema_only_db(live)  # real is_live_db_path -> False (a tmp file)
    with pytest.raises(LiveDbCertificationError, match="not the live/default DB"):
        run_live_db_provenance_audit(live_db_path=live, project_key="tropical")


def test_audit_does_not_modify_db_file(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    before = _content_sig(live)
    run_live_db_provenance_audit(live_db_path=live, project_key="tropical")
    assert _content_sig(live) == before


def test_audit_report_deterministic(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    work = tmp_path / "evidence"
    r1 = run_live_db_provenance_audit(live_db_path=live, work_root=work, project_key="tropical")
    raw = Path(r1["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"
    r2 = run_live_db_provenance_audit(live_db_path=live, work_root=work, project_key="tropical")
    assert Path(r2["report_path"]).read_text(encoding="utf-8") == raw  # unchanged DB -> identical


def test_audit_refuses_work_root_under_live_root(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    fake_live_root = tmp_path / "fake_live_root"
    monkeypatch.setattr(certmod, "_LIVE_ROOT", fake_live_root)
    with pytest.raises(LiveDbCertificationError, match="live forecast root"):
        run_live_db_provenance_audit(
            live_db_path=live, work_root=fake_live_root / "evidence", project_key="tropical"
        )


# --- 10-18. read-only certification ---------------------------------------------------


def test_cert_certified_match(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    report = run_live_db_readonly_certification(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, live_db_path=live
    )
    assert report["decision"] == CERT_MATCH
    for t in REQUIRED_TABLES:
        assert report["tables"][t]["match"] is True
        assert report["tables"][t]["raw_json_match"] is True
        assert report["tables"][t]["canonical_match"] is True


def test_cert_schema_only(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_schema_only_db(live)
    _flag_live(monkeypatch, live)
    report = run_live_db_readonly_certification(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, live_db_path=live
    )
    assert report["decision"] == "schema_only"


def test_cert_stale_or_mismatch(tmp_path, monkeypatch):
    # Live DB is projected from a MUTATED source; certify against the original -> mismatch.
    sp = _source_package(tmp_path / "src")
    sp2 = _source_package(tmp_path / "src2")
    bd = sp2 / "data" / "budget_details.jsonl"
    rows = [json.loads(line) for line in bd.read_text().splitlines() if line]
    rows[0]["amounts"]["projected_budget"] = 987654.0
    bd.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp2)
    _flag_live(monkeypatch, live)
    report = run_live_db_readonly_certification(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, live_db_path=live
    )
    assert report["decision"] == "stale_or_mismatch"
    assert report["tables"]["forecast_budget_details"]["match"] is False
    assert report["mismatch_summary"]


def test_cert_includes_counts_and_digests(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    report = run_live_db_readonly_certification(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, live_db_path=live
    )
    for t in REQUIRED_TABLES:
        e = report["tables"][t]
        assert e["live_rows"] > 0 and e["temp_rows"] > 0
        assert {
            "raw_json_digest_live",
            "raw_json_digest_temp",
            "canonical_digest_live",
            "canonical_digest_temp",
        } <= set(e)


def test_cert_report_deterministic(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    report = run_live_db_readonly_certification(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, live_db_path=live
    )
    raw = Path(report["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"
    assert loaded["schema_version"] == CERT_REPORT_SCHEMA_VERSION


def test_cert_refuses_unsafe_work_root(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    fake_live_root = tmp_path / "fake_live_root"
    monkeypatch.setattr(certmod, "_LIVE_ROOT", fake_live_root)
    with pytest.raises(LiveDbCertificationError, match="live forecast root"):
        run_live_db_readonly_certification(
            source_package=sp,
            work_root=fake_live_root / "work",
            context_stamp=STAMP,
            live_db_path=tmp_path / "live.sqlite",
        )


def test_cert_refuses_missing_source(tmp_path):
    with pytest.raises(LiveDbCertificationError, match="source_package not found"):
        run_live_db_readonly_certification(
            source_package=tmp_path / "src" / "twn_cost_forecast_json_package",
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=tmp_path / "live.sqlite",
        )


def test_cert_refuses_unreadable_live(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    live.parent.mkdir(parents=True)
    live.write_text("not a sqlite db", encoding="utf-8")
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbCertificationError, match="not a readable SQLite"):
        run_live_db_readonly_certification(
            source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, live_db_path=live
        )


def test_cert_does_not_write_live_db(tmp_path, monkeypatch):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    before = _content_sig(live)
    run_live_db_readonly_certification(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, live_db_path=live
    )
    assert _content_sig(live) == before


# --- 19-25. guarded live-DB certified-equivalence opt-in ------------------------------


def _real_certification(tmp_path, monkeypatch) -> tuple[Path, Path, Path]:
    """Produce a real certified_match report. Returns (source_package, live_db, cert_report_path)."""
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    cert = run_live_db_readonly_certification(
        source_package=sp, work_root=tmp_path / "cert", context_stamp=STAMP, live_db_path=live
    )
    assert cert["decision"] == CERT_MATCH
    return sp, live, Path(cert["report_path"])


def test_guarded_temp_path_still_works(tmp_path):
    sp = _source_package(tmp_path / "src")
    report = run_guarded_db_operator_run(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP
    )
    assert report["decision"] == "approved_for_guarded_db_context_analysis_use"
    assert "live_db" not in report


def test_guarded_refuses_live_db_without_flag(tmp_path, monkeypatch):
    sp, live, _cert = _real_certification(tmp_path, monkeypatch)
    with pytest.raises(GuardedDbOperatorRunError, match="live-DB opt-in requires"):
        run_guarded_db_operator_run(
            source_package=sp, work_root=tmp_path / "op", context_stamp=STAMP, db_path=live
        )


def test_guarded_refuses_flag_without_cert(tmp_path, monkeypatch):
    sp, live, _cert = _real_certification(tmp_path, monkeypatch)
    with pytest.raises(GuardedDbOperatorRunError, match="requires --live-db-certification"):
        run_guarded_db_operator_run(
            source_package=sp,
            work_root=tmp_path / "op",
            context_stamp=STAMP,
            db_path=live,
            allow_certified_live_db=True,
        )


def test_guarded_refuses_cert_not_match(tmp_path, monkeypatch):
    sp, live, _cert = _real_certification(tmp_path, monkeypatch)
    bad = tmp_path / "bad_cert.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "decision": "stale_or_mismatch",
                "project_key": "tropical",
                "live_db": str(live),
                "source_package": str(sp),
                "tables": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(GuardedDbOperatorRunError, match="not 'certified_match'"):
        run_guarded_db_operator_run(
            source_package=sp,
            work_root=tmp_path / "op",
            context_stamp=STAMP,
            db_path=live,
            allow_certified_live_db=True,
            live_db_certification=bad,
        )


def test_guarded_refuses_cert_diff_source(tmp_path, monkeypatch):
    sp, live, cert = _real_certification(tmp_path, monkeypatch)
    data = json.loads(cert.read_text())
    data["source_package"] = str(tmp_path / "other" / "twn_cost_forecast_json_package")
    cert.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuardedDbOperatorRunError, match="source_package does not match"):
        run_guarded_db_operator_run(
            source_package=sp,
            work_root=tmp_path / "op",
            context_stamp=STAMP,
            db_path=live,
            allow_certified_live_db=True,
            live_db_certification=cert,
        )


def test_guarded_refuses_cert_diff_live_db(tmp_path, monkeypatch):
    sp, live, cert = _real_certification(tmp_path, monkeypatch)
    data = json.loads(cert.read_text())
    data["live_db"] = str(tmp_path / "other_live.sqlite")
    cert.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuardedDbOperatorRunError, match="live_db does not match"):
        run_guarded_db_operator_run(
            source_package=sp,
            work_root=tmp_path / "op",
            context_stamp=STAMP,
            db_path=live,
            allow_certified_live_db=True,
            live_db_certification=cert,
        )


def test_guarded_allows_certified_live_db(tmp_path, monkeypatch):
    sp, live, cert = _real_certification(tmp_path, monkeypatch)
    before = _content_sig(live)
    report = run_guarded_db_operator_run(
        source_package=sp,
        work_root=tmp_path / "op",
        context_stamp=STAMP,
        db_path=live,
        allow_certified_live_db=True,
        live_db_certification=cert,
    )
    assert report["decision"] == "approved_for_guarded_db_context_analysis_use"
    assert report["live_db"]["certified"] is True
    assert report["live_db"]["used_for_execution"] is False
    assert report["live_db"]["equivalent_to_temp_db"] is True
    assert _same(report["live_db"]["live_db_path"], live)
    # execution used a fresh temp DB under the operator work root, not the live DB
    assert guarded._is_under(Path(report["temp_db"]["path"]), tmp_path / "op")
    assert _content_sig(live) == before  # live DB untouched by the guarded run


# --- 26-28. CLI -----------------------------------------------------------------------


def test_cli_audit_rc(tmp_path, monkeypatch, capsys):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    rc = cli.main(
        [
            "live-db-provenance-audit",
            "--project",
            "tropical",
            "--work-root",
            str(tmp_path / "ev"),
            "--live-db-path",
            str(live),
        ]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "populated_tropical"

    # missing v59 tables -> rc 1
    bare = tmp_path / "bare.sqlite"
    conn = sqlite3.connect(str(bare))
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)"
    )
    conn.execute("INSERT INTO schema_migrations VALUES (1, 'v1', '2025-01-01')")
    conn.commit()
    conn.close()
    _flag_live(monkeypatch, bare)
    rc1 = cli.main(
        ["live-db-provenance-audit", "--project", "tropical", "--live-db-path", str(bare)]
    )
    assert rc1 == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "missing_v59_tables"

    # missing DB -> rc 3
    rc3 = cli.main(
        [
            "live-db-provenance-audit",
            "--project",
            "tropical",
            "--live-db-path",
            str(tmp_path / "nope.sqlite"),
        ]
    )
    assert rc3 == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_cli_cert_rc(tmp_path, monkeypatch, capsys):
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, sp)
    _flag_live(monkeypatch, live)
    rc0 = cli.main(
        [
            "live-db-readonly-certification",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "w0"),
            "--context-stamp",
            STAMP,
            "--live-db-path",
            str(live),
        ]
    )
    assert rc0 == 0
    assert json.loads(capsys.readouterr().out)["decision"] == CERT_MATCH

    schema_only = tmp_path / "so.sqlite"
    _build_schema_only_db(schema_only)
    _flag_live(monkeypatch, schema_only)
    rc1 = cli.main(
        [
            "live-db-readonly-certification",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "w1"),
            "--context-stamp",
            STAMP,
            "--live-db-path",
            str(schema_only),
        ]
    )
    assert rc1 == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "schema_only"

    rc3 = cli.main(
        [
            "live-db-readonly-certification",
            "--project",
            "tropical",
            "--source-package",
            str(tmp_path / "missing" / "twn_cost_forecast_json_package"),
            "--work-root",
            str(tmp_path / "w3"),
            "--context-stamp",
            STAMP,
            "--live-db-path",
            str(live),
        ]
    )
    assert rc3 == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_cli_guarded_live_opt_in_rc(tmp_path, monkeypatch, capsys):
    sp, live, cert = _real_certification(tmp_path, monkeypatch)
    rc0 = cli.main(
        [
            "guarded-db-operator-run",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "op0"),
            "--context-stamp",
            STAMP,
            "--db-path",
            str(live),
            "--allow-certified-live-db",
            "--live-db-certification",
            str(cert),
        ]
    )
    assert rc0 == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "approved_for_guarded_db_context_analysis_use"
    assert payload["live_db"]["used_for_execution"] is False

    rc3 = cli.main(
        [
            "guarded-db-operator-run",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "op3"),
            "--context-stamp",
            STAMP,
            "--db-path",
            str(live),
        ]
    )
    assert rc3 == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_existing_cli_commands_still_route():
    parser = cli.build_parser()
    for cmd in ("run-context", "run-analysis"):
        assert parser.parse_args([cmd, "--project", "tropical"]).command == cmd
    gor = parser.parse_args(
        [
            "guarded-db-operator-run",
            "--project",
            "tropical",
            "--source-package",
            "/x",
            "--work-root",
            "/y",
            "--context-stamp",
            "s",
            "--db-path",
            "/z",
            "--allow-certified-live-db",
            "--live-db-certification",
            "/c",
        ]
    )
    assert gor.command == "guarded-db-operator-run"
    assert gor.allow_certified_live_db is True and gor.live_db_certification == "/c"
    lpa = parser.parse_args(["live-db-provenance-audit", "--project", "tropical"])
    assert lpa.command == "live-db-provenance-audit" and lpa.work_root is None
    lrc = parser.parse_args(
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
    )
    assert lrc.command == "live-db-readonly-certification" and lrc.live_db_path is None


# --- duplicated synthetic source fixture (mirrors Phase 11/12 build_fixture) -----------


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
