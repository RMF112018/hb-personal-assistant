"""Phase 2 forecast lineage projection: dry-run, apply, idempotency, NULL-sha dedup.

Synthetic CFR run-state + package fixtures projected into a temp v58 DB. No live DB,
no domain rows, no forecast-behavior coupling.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.forecast import projection_engine as eng
from hb_assistant.store.migrator import SQLiteMigrator

V58_TABLES = (
    "forecast_projects",
    "forecast_runs",
    "forecast_package_manifests",
    "forecast_source_ingestions",
    "forecast_validation_events",
)


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _context_manifest() -> dict:
    return {
        "package_name": "forecast_context_package_tropical_20260101_000000",
        "generated_stamp": "20260101_000000",
        "project": {"name": "Tropical", "project_key": "tropical", "job": "23-435-01"},
        "output_files": [
            {"path": "canonical/budget_codes.jsonl", "row_count": 127, "sha256": "out1"},
        ],
        "source_files": [
            {"label": "twn_budget_details", "path": "twn/budget_details.jsonl", "sha256": "src1"},
            {"label": "owner_pay_app", "path": "owner/pay.jsonl", "sha256": "src2"},
            # Two upstream sources WITHOUT sha256 — must each get a distinct fallback
            # hash (package|path), never collapse to one row.
            {"label": "nosha_a", "path": "x/a.jsonl"},
            {"label": "nosha_b", "path": "x/b.jsonl"},
        ],
        "validation_status": {
            "row_count_reconciliation": True,
            "json_validity": True,
            "safety_scan": True,
        },
        "conclusion": "forecast_context_ready",
    }


def _analysis_manifest() -> dict:
    return {
        "package_name": "forecast_analysis_package_tropical_20260101_000001",
        "generated_stamp": "20260101_000001",
        "project": {"name": "Tropical", "project_key": "tropical", "job": "23-435-01"},
        "output_files": [
            {"path": "analysis/discrepancies.jsonl", "row_count": 12, "sha256": "out2"}
        ],
        # Shares the src1 sha but a different package -> distinct ingestion (by design).
        "source_files": [{"label": "context", "path": "context.jsonl", "sha256": "src1"}],
        "validation_status": {"structural_ok": True},
        "conclusion": "forecast_analysis_ready",
    }


def _build_subproject(root: Path) -> Path:
    """Create a synthetic CFR subproject with a run-state and two packages. Returns run-state path."""
    data = root / "data"
    ctx_dir = data / _context_manifest()["package_name"]
    anl_dir = data / _analysis_manifest()["package_name"]
    _write_json(ctx_dir / "manifest.json", _context_manifest())
    _write_json(anl_dir / "manifest.json", _analysis_manifest())

    run_id = "20260101_000000"
    state = {
        "project_key": "tropical",
        "run_started_at_utc": "2026-01-01T00:00:00+00:00",
        "run_id": run_id,
        "data_root": str(data),
        "packages": {
            "context": {"path": str(ctx_dir), "stamp": "20260101_000000"},
            "analysis": {"path": str(anl_dir), "stamp": "20260101_000001"},
        },
    }
    state_path = root / ".cfr_run_state" / f"full_fresh_tropical_{run_id}.json"
    _write_json(state_path, state)
    _write_json(
        root / ".cfr_run_state" / "current_tropical.json",
        {"active_run_state": str(state_path), "run_id": run_id},
    )
    return state_path


def _migrated_v58_db(path: Path) -> str:
    assert SQLiteMigrator(db_path=str(path)).apply() >= 58
    return str(path)


def _counts(db: str) -> dict[str, int]:
    conn = sqlite3.connect(db)
    try:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in V58_TABLES}
    finally:
        conn.close()


# Expected planned counts for the two-package fixture.
EXPECTED = {
    "forecast_projects": 1,
    "forecast_runs": 1,
    "forecast_package_manifests": 2,
    "forecast_source_ingestions": 5,  # context: 4 (incl. 2 fallback-sha) + analysis: 1
    "forecast_validation_events": 4,  # context: 3 + analysis: 1
}


def test_dry_run_plans_without_touching_db(tmp_path: Path) -> None:
    state_path = _build_subproject(tmp_path)
    db = _migrated_v58_db(tmp_path / "v58.db")  # exists but must stay empty

    receipt = eng.project_run(run_state_path=state_path, apply=False)

    assert receipt["mode"] == "dry_run"
    assert receipt["ok"] is True
    assert receipt["project_key"] == "tropical"
    assert receipt["run_id"] == "20260101_000000"
    assert receipt["counts"] == {
        "projects": 1,
        "runs": 1,
        "package_manifests": 2,
        "source_ingestions": 5,
        "validation_events": 4,
    }
    # Dry-run wrote nothing to the (separately migrated) DB.
    assert _counts(db) == dict.fromkeys(V58_TABLES, 0)


def test_apply_requires_explicit_db_path(tmp_path: Path) -> None:
    state_path = _build_subproject(tmp_path)
    receipt = eng.project_run(run_state_path=state_path, apply=True, db_path=None)
    assert receipt["mode"] == "apply"
    assert receipt["ok"] is False
    assert receipt["reason"] == "apply_requires_explicit_db_path"


def test_apply_writes_all_five_tables(tmp_path: Path) -> None:
    state_path = _build_subproject(tmp_path)
    db = _migrated_v58_db(tmp_path / "v58.db")

    receipt = eng.project_run(run_state_path=state_path, apply=True, db_path=Path(db))

    assert receipt["mode"] == "apply"
    assert receipt["ok"] is True
    assert _counts(db) == EXPECTED


def test_apply_is_idempotent(tmp_path: Path) -> None:
    state_path = _build_subproject(tmp_path)
    db = _migrated_v58_db(tmp_path / "v58.db")

    eng.project_run(run_state_path=state_path, apply=True, db_path=Path(db))
    first = _counts(db)
    eng.project_run(run_state_path=state_path, apply=True, db_path=Path(db))
    second = _counts(db)

    assert first == EXPECTED
    assert second == EXPECTED  # re-projection upserts, never duplicates


def test_null_sha_sources_stay_distinct(tmp_path: Path) -> None:
    state_path = _build_subproject(tmp_path)
    db = _migrated_v58_db(tmp_path / "v58.db")
    eng.project_run(run_state_path=state_path, apply=True, db_path=Path(db))

    conn = sqlite3.connect(db)
    try:
        # The two sha-less context sources must NOT collapse: 4 distinct ingestions for the context package.
        ctx_pkg = "forecast_context_package_tropical_20260101_000000"
        n_ctx = conn.execute(
            "SELECT COUNT(*) FROM forecast_source_ingestions WHERE source_package=?", (ctx_pkg,)
        ).fetchone()[0]
        assert n_ctx == 4
        n_distinct_sha = conn.execute(
            "SELECT COUNT(DISTINCT source_sha256) FROM forecast_source_ingestions WHERE source_package=?",
            (ctx_pkg,),
        ).fetchone()[0]
        assert n_distinct_sha == 4
    finally:
        conn.close()


def test_resolves_via_current_pointer(tmp_path: Path) -> None:
    _build_subproject(tmp_path)
    db = _migrated_v58_db(tmp_path / "v58.db")
    # No explicit run_state_path: resolve through subproject_root + current_<project> pointer.
    receipt = eng.project_run(
        subproject_root=tmp_path, project_key="tropical", apply=True, db_path=Path(db)
    )
    assert receipt["ok"] is True
    assert _counts(db) == EXPECTED


def test_validation_event_seq_is_stable_and_prefixed(tmp_path: Path) -> None:
    state_path = _build_subproject(tmp_path)
    receipt = eng.project_run(run_state_path=state_path, apply=False)
    events = receipt["planned"]["validation_events"]
    seqs = [e["event_seq"] for e in events]
    assert seqs == [1, 2, 3, 4]  # monotonic, context (stamp ..0000) before analysis (..0001)
    assert all(":" in e["gate_name"] for e in events)  # package-type-prefixed gate names
