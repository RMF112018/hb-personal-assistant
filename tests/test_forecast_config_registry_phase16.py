"""Phase 16 — governed forecast config registry (v60) + opt-in CFR_CONFIG_ROOT bridge.

Covers the v60 migration (idempotent), import (JSON/JSONL/CSV, order, duplicate-key + invalid-input fail
closed), snapshot immutability, export + materialize, import->export reader-layer parity, the
CFR_CONFIG_ROOT opt-in bridge (unset/set/missing/relative, scoped+restored), validate-crosswalk file vs
DB-snapshot parity, live-DB import gating, and the Phase 9/12/15 lineage-only metadata block. Synthetic
config + synthetic temp DBs only; the real live DB is never touched.
"""

from __future__ import annotations

import inspect
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality.table_inventory import build_table_inventory_report
from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review import config_registry as cr  # noqa: E402
from construction_financial_review.common import config_root as crootmod  # noqa: E402
from construction_financial_review.common.config_root import (  # noqa: E402
    ConfigRootError,
    resolve_config_base,
)
from construction_financial_review.forecast_controls import load_controls  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    controlled_db_context_analysis,
    db_certified_final_output,
    guarded_db_operator_run,
)

controls_loader = load_controls
phase9 = controlled_db_context_analysis
phase12 = guarded_db_operator_run
phase15 = db_certified_final_output

V60_TABLES = (
    "forecast_config_sources",
    "forecast_config_items",
    "forecast_config_snapshots",
    "forecast_config_snapshot_items",
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


# --- synthetic config fixture ----------------------------------------------------------


def _wjsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def build_config(root: Path) -> Path:
    """Synthetic config tree; returns the base (dir containing config/)."""
    c = root / "config"
    (c / "projects").mkdir(parents=True, exist_ok=True)
    (c / "projects" / "tropical.json").write_text(
        json.dumps(
            {
                "project_key": "tropical",
                "owner_sov_scope_crosswalk": "config/crosswalks/tropical/xw.jsonl",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _wjsonl(
        c / "forecast_controls" / "tropical" / "code_forecast_controls.jsonl",
        [
            {"project_key": "tropical", "control_id": "ctl-1", "cost_code": "03-01"},
            {"project_key": "tropical", "control_id": "ctl-2", "cost_code": "03-02"},
        ],
    )
    _wjsonl(
        c / "forecast_model_controls" / "tropical" / "code_forecast_model_controls.jsonl",
        [{"project_key": "tropical", "control_id": "mc-1", "effective_month": "2026-06"}],
    )
    _wjsonl(
        c / "forecast_staffing" / "tropical" / "staffing_budget_code_mapping.jsonl",
        [
            {
                "project_key": "tropical",
                "source_cost_code": "10-01",
                "target_budget_code_key": "1000.10-01.LAB",
            }
        ],
    )
    xw = [
        {"crosswalk_id": "xw-1", "owner_sov_code": "A", "covered_budget_code_keys": ["k1"]},
        {"crosswalk_id": "xw-2", "owner_sov_code": "B", "covered_budget_code_keys": ["k2", "k3"]},
    ]
    _wjsonl(c / "crosswalks" / "tropical" / "xw.jsonl", xw)
    (c / "crosswalks" / "tropical" / "xw.csv").write_text(
        "crosswalk_id,owner_sov_code\nxw-1,A\nxw-2,B\n", encoding="utf-8"
    )
    return root


def _migrated_db(path: Path) -> Path:
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _import(base: Path, db: Path, run_id="t") -> dict:
    return cr.import_forecast_config_to_db(
        config_root=base, db_path=db, project_key="tropical", import_run_id=run_id
    )


# --- 1-4. migration / schema / lifecycle ----------------------------------------------


def test_migration_creates_v60_tables(tmp_path):
    db = _migrated_db(tmp_path / "v60.db")
    conn = sqlite3.connect(str(db))
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for t in V60_TABLES:
        assert t in names


def test_migration_idempotent(tmp_path):
    db = tmp_path / "v60.db"
    SQLiteMigrator(db_path=str(db)).apply()
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=60").fetchone()[0]
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()
    assert n == 1


def test_latest_schema_version_is_at_least_60():
    # Phase 16 introduced v60; later phases bump further (Phase 4 -> v61).
    assert LATEST_SCHEMA_VERSION >= 60


def test_lifecycle_contract_count_and_classification():
    assert build_table_inventory_report(db_path=None)["contract_table_count"] == 399
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["table_count"] == 399
    assert contract["table_count"] == len(contract["tables"])
    for t in V60_TABLES:
        entry = contract["tables"][t]
        assert entry["table_family"] == "forecast_config_registry_v60"
        assert entry["lifecycle_status"] == "operational_empty_expected"
        assert entry["v"] == "V60"


# --- 5-11. import ----------------------------------------------------------------------


def test_import_json_jsonl_csv_and_counts(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    rep = _import(base, db)
    assert rep["source_count"] == 6  # project, controls, model, staffing, crosswalk jsonl + csv
    by_domain = {(s["config_domain"], s["source_format"]): s for s in rep["sources"]}
    assert by_domain[("project", "json")]["row_count"] == 1
    assert by_domain[("forecast_controls", "jsonl")]["row_count"] == 2
    assert by_domain[("owner_sov_crosswalk", "csv")]["row_count"] == 2
    for s in rep["sources"]:
        assert len(s["source_sha256"]) == 64 and len(s["content_sha256"]) == 64
        assert s["source_path"].startswith("config/")


def test_import_jsonl_preserves_order(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT item_key, item_order FROM forecast_config_items "
        "WHERE config_domain='forecast_controls' ORDER BY item_order"
    ).fetchall()
    conn.close()
    assert rows == [("ctl-1", 0), ("ctl-2", 1)]


def test_import_csv_preserves_order(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT item_key, item_order FROM forecast_config_items "
        "WHERE config_domain='owner_sov_crosswalk' AND config_name LIKE '%.csv' ORDER BY item_order"
    ).fetchall()
    conn.close()
    assert [r[1] for r in rows] == [0, 1]


def test_import_invalid_jsonl_reports_file_and_line(tmp_path):
    base = build_config(tmp_path / "cfg")
    bad = base / "config" / "forecast_controls" / "tropical" / "code_forecast_controls.jsonl"
    bad.write_text('{"control_id": "ok"}\n{bad json}\n', encoding="utf-8")
    db = _migrated_db(tmp_path / "reg.db")
    with pytest.raises(
        cr.ConfigRegistryError, match=r"code_forecast_controls\.jsonl:2: invalid JSON"
    ):
        _import(base, db)


def test_import_invalid_project_json_reports_file(tmp_path):
    base = build_config(tmp_path / "cfg")
    (base / "config" / "projects" / "tropical.json").write_text("{not json", encoding="utf-8")
    db = _migrated_db(tmp_path / "reg.db")
    with pytest.raises(
        cr.ConfigRegistryError, match=r"tropical\.json.*invalid JSON|project config"
    ):
        _import(base, db)


def test_import_duplicate_item_key_fails_closed(tmp_path):
    base = build_config(tmp_path / "cfg")
    dup = base / "config" / "forecast_controls" / "tropical" / "code_forecast_controls.jsonl"
    _wjsonl(dup, [{"control_id": "x"}, {"control_id": "x"}])
    db = _migrated_db(tmp_path / "reg.db")
    with pytest.raises(cr.ConfigRegistryError, match="duplicate item_key"):
        _import(base, db)


def test_import_idempotent(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    _import(base, db)  # re-import same content
    conn = sqlite3.connect(str(db))
    items = conn.execute("SELECT COUNT(*) FROM forecast_config_items").fetchone()[0]
    sources = conn.execute("SELECT COUNT(*) FROM forecast_config_sources").fetchone()[0]
    conn.close()
    # project1 + controls2 + model1 + staffing1 + xw_jsonl2 + xw_csv2 = 9; re-import must not duplicate.
    assert sources == 6 and items == 9


# --- 12-16. export / snapshot / materialize -------------------------------------------


def test_export_creates_file_tree_and_roundtrips(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    exp = cr.export_forecast_config_from_db(
        db_path=db, out_root=tmp_path / "exp", project_key="tropical"
    )
    assert len(exp["files"]) == 6
    # Re-import the exported tree into a fresh DB and compare item canonical hashes.
    db2 = _migrated_db(tmp_path / "reg2.db")
    _import(tmp_path / "exp", db2)

    def _hashes(d):
        conn = sqlite3.connect(str(d))
        rows = conn.execute(
            "SELECT config_domain, item_order, canonical_json_sha256 FROM forecast_config_items "
            "ORDER BY config_domain, config_name, item_order"
        ).fetchall()
        conn.close()
        return rows

    assert _hashes(db) == _hashes(db2)


def test_snapshot_is_immutable_with_manifest_hashes(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="s1", snapshot_reason="r"
    )
    assert len(snap["snapshot_sha256"]) == 64
    assert snap["counts_by_domain"]["forecast_controls"] == 2
    assert "forecast_controls" in snap["hashes_by_domain"]
    conn = sqlite3.connect(str(db))
    si = conn.execute(
        "SELECT COUNT(*) FROM forecast_config_snapshot_items WHERE config_snapshot_id=?",
        (snap["config_snapshot_id"],),
    ).fetchone()[0]
    conn.close()
    assert si == snap["item_count"]


def test_materialized_snapshot_is_file_compatible(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="s1", snapshot_reason="r"
    )
    mat = cr.materialize_forecast_config_snapshot(
        db_path=db, config_snapshot_id=snap["config_snapshot_id"], out_root=tmp_path / "mat"
    )
    mat_base = Path(mat["materialized_config_root"])
    # the existing readers parse the materialized tree identically to the repo tree
    cfg = json.loads((mat_base / "config/projects/tropical.json").read_text())
    assert cfg["project_key"] == "tropical"
    mat_lines = (
        mat_base / "config/forecast_controls/tropical/code_forecast_controls.jsonl"
    ).read_text()
    assert mat_lines.strip().count("\n") == 1  # 2 lines
    # control_file_path resolves under the materialized base when CFR_CONFIG_ROOT points at it
    assert controls_loader.control_file_path(cfg, mat_base).is_file()


# --- 17-19. resolver -------------------------------------------------------------------


def test_resolver_file_mode(tmp_path):
    base = build_config(tmp_path / "cfg")
    res = cr.resolve_forecast_config(source_mode="file", config_root=base)
    assert res.source_mode == "file"
    assert res.config_root == base.resolve() or res.config_root == base


def test_resolver_db_snapshot_mode_not_repo(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="s1", snapshot_reason="r"
    )
    res = cr.resolve_forecast_config(
        source_mode="db_snapshot",
        db_path=db,
        config_snapshot_id=snap["config_snapshot_id"],
        work_root=tmp_path / "mat",
    )
    assert res.source_mode == "db_snapshot"
    assert res.config_snapshot_id == snap["config_snapshot_id"]
    # the resolved config root is the materialized tree, NOT the repo config base
    assert Path("config") != res.config_root
    assert (tmp_path / "cfg") not in res.config_root.parents
    assert res.row_counts and res.hashes


# --- 20. CFR_CONFIG_ROOT bridge redirects the real readers ------------------------------


def test_cfr_config_root_unset_is_unchanged(tmp_path):
    # unset -> resolve_config_base returns the passed subproject_root verbatim
    assert resolve_config_base(tmp_path) == tmp_path


def test_cfr_config_root_redirects_reader(tmp_path, monkeypatch):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="s1", snapshot_reason="r"
    )
    mat = cr.materialize_forecast_config_snapshot(
        db_path=db, config_snapshot_id=snap["config_snapshot_id"], out_root=tmp_path / "mat"
    )
    monkeypatch.setenv(crootmod.ENV_CONFIG_ROOT, mat["materialized_config_root"])
    # control_file_path now resolves under the materialized root (subproject_root is ignored)
    p = controls_loader.control_file_path({}, Path("/nonexistent/subproject"))
    assert str(p).startswith(mat["materialized_config_root"])
    assert p.is_file()


def test_cfr_config_root_missing_fails_closed(monkeypatch):
    monkeypatch.setenv(crootmod.ENV_CONFIG_ROOT, "/no/such/dir/zzz")
    with pytest.raises(ConfigRootError, match="does not exist"):
        resolve_config_base(Path("/tmp"))


def test_cfr_config_root_relative_fails_closed(monkeypatch):
    monkeypatch.setenv(crootmod.ENV_CONFIG_ROOT, "relative/path")
    with pytest.raises(ConfigRootError, match="absolute"):
        resolve_config_base(Path("/tmp"))


# --- 24-25. reader-layer parity --------------------------------------------------------


def test_db_parity_passes(tmp_path):
    base = build_config(tmp_path / "cfg")
    rep = cr.run_forecast_config_db_parity(config_root=base, work_root=tmp_path / "par")
    assert rep["status"] == "pass"
    assert all(d["match"] for d in rep["domains"].values())


def test_db_parity_mismatch_reports_differences(tmp_path, monkeypatch):
    base = build_config(tmp_path / "cfg")
    real_mat = cr.materialize_forecast_config_snapshot

    def _tamper(**kw):
        out = real_mat(**kw)
        # corrupt one materialized file so file-vs-db records differ
        f = (
            Path(out["materialized_config_root"])
            / "config/forecast_controls/tropical/code_forecast_controls.jsonl"
        )
        f.write_text('{"control_id": "TAMPERED"}\n', encoding="utf-8")
        return out

    monkeypatch.setattr(cr, "materialize_forecast_config_snapshot", _tamper)
    rep = cr.run_forecast_config_db_parity(config_root=base, work_root=tmp_path / "par")
    assert rep["status"] == "fail"
    assert any("forecast_controls" in d for d in rep["differences"])


# --- 26-29. live-DB gating + no mutation -----------------------------------------------


def _flag_live(monkeypatch, db: Path):
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: Path(p).resolve() == db.resolve())


def test_live_import_refused_without_flag(tmp_path, monkeypatch):
    base = build_config(tmp_path / "cfg")
    live = _migrated_db(tmp_path / "live.db")
    _flag_live(monkeypatch, live)
    with pytest.raises(cr.ConfigRegistryError, match="allow_live_db_write"):
        cr.import_forecast_config_to_db(config_root=base, db_path=live, project_key="tropical")


def test_synthetic_live_import_succeeds_with_flag(tmp_path, monkeypatch):
    base = build_config(tmp_path / "cfg")
    live = _migrated_db(tmp_path / "live.db")  # pre-migrated (Phase 16 never migrates the live DB)
    _flag_live(monkeypatch, live)
    rep = cr.import_forecast_config_to_db(
        config_root=base, db_path=live, project_key="tropical", allow_live_db_write=True
    )
    assert rep["safety"]["live_db_written"] is True
    assert rep["safety"]["live_db_migrated"] is False


def test_non_live_import_needs_no_flag(tmp_path, monkeypatch):
    base = build_config(tmp_path / "cfg")
    db = tmp_path / "reg.db"  # not migrated; import auto-migrates non-live
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: False)
    rep = _import(base, db)
    assert rep["source_count"] == 6


def test_source_config_not_mutated(tmp_path):
    base = build_config(tmp_path / "cfg")

    def _sig(root):
        return {
            str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
        }

    before = _sig(base)
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="s1", snapshot_reason="r"
    )
    cr.materialize_forecast_config_snapshot(
        db_path=db, config_snapshot_id=snap["config_snapshot_id"], out_root=tmp_path / "mat"
    )
    cr.export_forecast_config_from_db(db_path=db, out_root=tmp_path / "exp", project_key="tropical")
    assert _sig(base) == before


# --- Phase 9/12/15 lineage metadata (metadata-only) ------------------------------------


def test_lineage_block_labels_not_consumed(tmp_path):
    base = build_config(tmp_path / "cfg")
    db = _migrated_db(tmp_path / "reg.db")
    _import(base, db)
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="s1", snapshot_reason="r"
    )
    cr.materialize_forecast_config_snapshot(
        db_path=db, config_snapshot_id=snap["config_snapshot_id"], out_root=tmp_path / "mat"
    )
    block = cr.config_snapshot_lineage_block(tmp_path / "mat")
    assert block["config_snapshot_consumed"] is False
    assert block["config_snapshot_attached_for_lineage"] is True
    assert block["config_consuming_components"] == []
    assert "does not read operator config" in block["config_not_consumed_reason"]
    assert block["config_snapshot_id"] == snap["config_snapshot_id"]


def test_chain_workflows_accept_config_snapshot_root_param():
    for fn in (
        phase9.run_controlled_context_analysis_workflow,
        phase12.run_guarded_db_operator_run,
        phase15.run_db_certified_final_output,
    ):
        assert "config_snapshot_root" in inspect.signature(fn).parameters


# --- CLI rc 0/1/3 ----------------------------------------------------------------------


def test_cli_import_snapshot_parity_rc(tmp_path, capsys):
    base = build_config(tmp_path / "cfg")
    db = tmp_path / "reg.db"
    rc = cli.main(
        [
            "forecast-config-import",
            "--project",
            "tropical",
            "--config-root",
            str(base),
            "--db-path",
            str(db),
            "--import-run-id",
            "cli",
        ]
    )
    assert rc == 0
    capsys.readouterr()
    rc = cli.main(
        [
            "forecast-config-db-parity",
            "--project",
            "tropical",
            "--config-root",
            str(base),
            "--work-root",
            str(tmp_path / "par"),
        ]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


def test_cli_import_refusal_rc3_live(tmp_path, monkeypatch, capsys):
    base = build_config(tmp_path / "cfg")
    live = _migrated_db(tmp_path / "live.db")
    _flag_live(monkeypatch, live)
    rc = cli.main(
        [
            "forecast-config-import",
            "--project",
            "tropical",
            "--config-root",
            str(base),
            "--db-path",
            str(live),
        ]
    )
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_cli_existing_commands_still_route():
    parser = cli.build_parser()
    assert (
        parser.parse_args(["validate-crosswalk", "--project", "tropical"]).command
        == "validate-crosswalk"
    )
    a = parser.parse_args(
        [
            "validate-crosswalk",
            "--project",
            "tropical",
            "--config-source",
            "db_snapshot",
            "--config-db-path",
            "/d",
            "--config-snapshot-id",
            "s",
            "--config-snapshot-root",
            "/r",
        ]
    )
    assert a.config_source == "db_snapshot"
    assert (
        parser.parse_args(
            [
                "forecast-config-import",
                "--project",
                "tropical",
                "--config-root",
                "/c",
                "--db-path",
                "/d",
            ]
        ).command
        == "forecast-config-import"
    )
    assert (
        parser.parse_args(
            [
                "forecast-config-db-parity",
                "--project",
                "tropical",
                "--config-root",
                "/c",
                "--work-root",
                "/w",
            ]
        ).command
        == "forecast-config-db-parity"
    )


def test_real_live_db_not_our_temp(tmp_path):
    # sanity: our synthetic temp DBs never resolve to the real live/default DB
    db = tmp_path / "reg.db"
    assert dbeng.is_live_db_path(db) is False
