"""Phase E2 — CFR config-registry promotion workflow tests (gated live write).

A synthetic config DB is treated as "live" by monkeypatching ``source_domain_engine.is_live_db_path``
so the gated write path executes against a temp fixture; the real live DB is never touched. Proves the
additive certified promotion, the byte backup, expected-match + gate refusals, and rollback safety.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos" / "construction-financial-review" / "src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

from construction_financial_review.config_registry import (  # noqa: E402
    create_forecast_config_snapshot,
    import_forecast_config_to_db,
)
from construction_financial_review.workflows import live_db_certification as cert  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    live_db_config_registry_promotion as promo,
)

from hb_assistant.construction.forecast import source_domain_engine as dbeng  # noqa: E402
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402


def _build_config_tree(root: Path, *, model_value: str = "1000.00") -> None:
    cfg = root / "config"
    (cfg / "projects").mkdir(parents=True)
    (cfg / "forecast_model_controls" / "tropical").mkdir(parents=True)
    project = {
        "project_key": "tropical",
        "project_name": "TWN",
        "materiality_absolute": "25000.00",
    }
    (cfg / "projects" / "tropical.json").write_text(json.dumps(project), encoding="utf-8")
    (cfg / "forecast_model_controls" / "tropical" / "code_forecast_model_controls.jsonl").write_text(
        json.dumps({"project_key": "tropical", "control_id": "C-001", "explicit_value_amount": model_value})
        + "\n",
        encoding="utf-8",
    )


def _checkpoint(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _build_live_config_db(path: Path) -> None:
    SQLiteMigrator(db_path=str(path)).apply()
    _checkpoint(path)


def _seed_other_snapshot(path: Path, snapshot_id: str, project_key: str) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "INSERT INTO forecast_config_snapshots (config_snapshot_id, project_key, snapshot_name, "
            "snapshot_created_utc, snapshot_reason, source_mode, item_count, snapshot_sha256, "
            "created_by, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (snapshot_id, project_key, "seed", "2026-01-01T00:00:00+00:00", "seed", "db_current", 0,
             f"sha-{snapshot_id}", None, "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _expected(edited_root: Path, tmp_path: Path, name: str) -> tuple[int, dict]:
    """Compute the approved proposal's item_count + hashes_by_domain via a throwaway temp DB."""
    db = tmp_path / "expect.sqlite"
    import_forecast_config_to_db(config_root=edited_root, db_path=db, project_key="tropical")
    snap = create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name=name, snapshot_reason="r"
    )
    return int(snap["item_count"]), dict(snap["hashes_by_domain"])


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    edited = tmp_path / "edited_config"
    _build_config_tree(edited)
    live = tmp_path / "live.sqlite"
    _build_live_config_db(live)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: Path(p).resolve() == live.resolve())
    item_count, hashes = _expected(edited, tmp_path / "exp", "promotion_x")
    return {"edited": edited, "live": live, "work": tmp_path / "work", "item_count": item_count, "hashes": hashes}


def _run(ctx, **over):
    kwargs = {
        "edited_config_root": ctx["edited"],
        "work_root": ctx["work"],
        "context_stamp": "20260621_120000",
        "live_db_path": ctx["live"],
        "allow_live_db_write": True,
        "snapshot_name": "promotion_x",
        "snapshot_reason": "certified live promotion",
        "expected_item_count": ctx["item_count"],
        "expected_hashes_by_domain": ctx["hashes"],
    }
    kwargs.update(over)
    return promo.run_live_db_config_registry_promotion(**kwargs)


def _snapshot_count(live: Path) -> int:
    conn = cert._ro_conn(live)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM forecast_config_snapshots").fetchone()[0])
    finally:
        conn.close()


# -- happy path ---------------------------------------------------------------


def test_happy_path_certified_additive(ctx) -> None:
    report = _run(ctx)
    assert report["decision"] == promo.DECISION_CERTIFIED
    assert report["status"] == "ready"
    assert report["snapshots_before"] == 0
    assert report["snapshots_after"] == 1
    assert report["promotion_certification"]["decision"] == "certified_match"
    assert report["safety"]["additive_only"] is True
    assert Path(report["backup"]["path"]).exists()
    # The promoted snapshot is present in the live DB.
    assert _snapshot_count(ctx["live"]) == 1


def test_preserves_other_snapshots(ctx) -> None:
    _seed_other_snapshot(ctx["live"], "base-tropical", "tropical")
    _seed_other_snapshot(ctx["live"], "other-proj", "other")
    report = _run(ctx)
    assert report["decision"] == promo.DECISION_CERTIFIED
    assert report["snapshots_before"] == 2
    assert report["snapshots_after"] == 3
    assert report["promotion_certification"]["pre_existing_snapshots_preserved"] is True
    # Both seeded snapshots still present and unchanged.
    conn = cert._ro_conn(ctx["live"])
    try:
        ids = {r[0] for r in conn.execute("SELECT config_snapshot_id FROM forecast_config_snapshots")}
    finally:
        conn.close()
    assert {"base-tropical", "other-proj"} <= ids


# -- gate refusals (fail closed, no write) ------------------------------------


def test_missing_allow_live_db_write_refused(ctx) -> None:
    with pytest.raises(promo.LiveDbConfigRegistryPromotionError, match="allow_live_db_write"):
        _run(ctx, allow_live_db_write=False)
    assert _snapshot_count(ctx["live"]) == 0


def test_non_live_db_refused(ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: False)
    with pytest.raises(promo.LiveDbConfigRegistryPromotionError, match="not the live"):
        _run(ctx)
    assert _snapshot_count(ctx["live"]) == 0


def test_expected_item_count_mismatch_refused_before_backup(ctx) -> None:
    with pytest.raises(promo.LiveDbConfigRegistryPromotionError, match="item_count"):
        _run(ctx, expected_item_count=ctx["item_count"] + 5)
    assert _snapshot_count(ctx["live"]) == 0
    assert not (ctx["work"] / promo.BACKUP_SUBDIR / promo.BACKUP_NAME).exists()


def test_expected_hash_mismatch_refused_before_backup(ctx) -> None:
    with pytest.raises(promo.LiveDbConfigRegistryPromotionError, match="hashes_by_domain"):
        _run(ctx, expected_hashes_by_domain={"project": "deadbeef"})
    assert _snapshot_count(ctx["live"]) == 0
    assert not (ctx["work"] / promo.BACKUP_SUBDIR / promo.BACKUP_NAME).exists()


def test_double_promote_refused(ctx) -> None:
    _run(ctx)  # first promotion commits
    _checkpoint(ctx["live"])  # checkpoint so the backup's WAL guard passes on the second run
    # Second run uses a fresh work_root (deterministic temp), same edited config → same snapshot id.
    with pytest.raises(promo.LiveDbConfigRegistryPromotionError, match="double-promote"):
        _run(ctx, work_root=ctx["work"].parent / "work2")
    assert _snapshot_count(ctx["live"]) == 1  # unchanged


def test_active_item_duplication_guard(ctx, tmp_path: Path) -> None:
    # Pre-seed the live DB with the BASE config's active items, then promote an EDITED config.
    # The promoted snapshot must contain only the edited config's items (built in temp), not base+edited.
    import_forecast_config_to_db(
        config_root=ctx["edited"], db_path=ctx["live"], project_key="tropical",
        allow_live_db_write=True,
    )
    _checkpoint(ctx["live"])  # checkpoint after the direct import so the backup WAL guard passes
    report = _run(ctx)
    assert report["item_count"] == ctx["item_count"]  # not doubled
    assert report["decision"] == promo.DECISION_CERTIFIED


# -- colliding-source regression (ADR 283 defect → ADR 284 fix) ---------------


def _build_multi_config_tree(root: Path, controls: dict[str, str]) -> None:
    """A config tree with MULTIPLE model_controls items in one jsonl file (+ a project)."""
    cfg = root / "config"
    (cfg / "projects").mkdir(parents=True)
    (cfg / "forecast_model_controls" / "tropical").mkdir(parents=True)
    (cfg / "projects" / "tropical.json").write_text(
        json.dumps({"project_key": "tropical", "project_name": "TWN", "materiality_absolute": "25000.00"}),
        encoding="utf-8",
    )
    lines = "".join(
        json.dumps({"project_key": "tropical", "control_id": k, "explicit_value_amount": v}) + "\n"
        for k, v in controls.items()
    )
    (cfg / "forecast_model_controls" / "tropical" / "code_forecast_model_controls.jsonl").write_text(
        lines, encoding="utf-8"
    )


def _orphan_count(live: Path, snapshot_id: str) -> int:
    conn = cert._ro_conn(live)
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM forecast_config_snapshot_items si WHERE si.config_snapshot_id=? "
                "AND NOT EXISTS (SELECT 1 FROM forecast_config_items ci "
                "JOIN forecast_config_sources s ON s.config_source_id=ci.config_source_id "
                "WHERE ci.config_item_id=si.config_item_id)",
                (snapshot_id,),
            ).fetchone()[0]
        )
    finally:
        conn.close()


def _promote(live: Path, edited: Path, work: Path, tmp_path: Path, name: str, stamp: str) -> dict:
    ic, h = _expected(edited, tmp_path / f"exp_{name}", name)
    return promo.run_live_db_config_registry_promotion(
        edited_config_root=edited, work_root=work, context_stamp=stamp, live_db_path=live,
        allow_live_db_write=True, snapshot_name=name, snapshot_reason="r",
        expected_item_count=ic, expected_hashes_by_domain=h,
    )


def test_colliding_source_same_path_different_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Promoting an edit into a live DB that already holds a content-identical prior snapshot must NOT
    orphan the unchanged items. Reproduces the ADR 283 defect (4-of-5 model_controls orphaned)."""
    live = tmp_path / "live.sqlite"
    _build_live_config_db(live)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: Path(p).resolve() == live.resolve())

    # First promotion: BASE config (3 model_controls items + project) into the live DB.
    base = tmp_path / "base_config"
    _build_multi_config_tree(base, {"C-001": "1000.00", "C-002": "2000.00", "C-003": "3000.00"})
    _promote(live, base, tmp_path / "work_base", tmp_path, "promotion_base", "20260101_000000")
    _checkpoint(live)

    # Second promotion: EDITED config — same source_path, only C-002 changed (1 of 3).
    edited = tmp_path / "edited_config"
    _build_multi_config_tree(edited, {"C-001": "1000.00", "C-002": "2500.00", "C-003": "3000.00"})
    report = _promote(live, edited, tmp_path / "work_edited", tmp_path, "promotion_edited", "20260101_000001")
    promoted_id = report["promoted_snapshot_id"]

    # (a) No orphaned snapshot_items — the unchanged C-001/C-003 must resolve to a present item+source.
    assert _orphan_count(live, promoted_id) == 0
    assert report["item_count"] == 4  # C-001, C-002, C-003 + project

    # (b) The promoted snapshot round-trips: materialize -> reimport -> resnap == stored digest+count.
    from construction_financial_review.config_registry import (
        materialize_forecast_config_snapshot_readonly,
    )

    mat = materialize_forecast_config_snapshot_readonly(
        db_path=live, config_snapshot_id=promoted_id, out_root=tmp_path / "mat"
    )
    rdb = tmp_path / "round.sqlite"
    import_forecast_config_to_db(
        config_root=Path(mat["materialized_config_root"]), db_path=rdb, project_key="tropical"
    )
    resnap = create_forecast_config_snapshot(
        db_path=rdb, project_key="tropical", snapshot_name="rt", snapshot_reason="rt"
    )
    conn = cert._ro_conn(live)
    try:
        stored = conn.execute(
            "SELECT item_count, snapshot_sha256 FROM forecast_config_snapshots WHERE config_snapshot_id=?",
            (promoted_id,),
        ).fetchone()
    finally:
        conn.close()
    assert int(resnap["item_count"]) == int(stored[0])
    assert str(resnap["snapshot_sha256"]) == str(stored[1])

    # (c) Certified (the round-trip cert passes once the copy preserves linkage).
    assert report["decision"] == promo.DECISION_CERTIFIED
    assert report["snapshots_before"] == 1
    assert report["snapshots_after"] == 2
