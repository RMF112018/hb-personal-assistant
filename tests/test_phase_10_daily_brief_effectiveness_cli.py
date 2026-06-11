"""Phase 10 V52 — effectiveness CLI tests (dry-run/apply posture, exits, no-mutation, raw-free)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai.model_eval_metrics import (
    scan_text_for_forbidden,
)
from tests._phase_10_effectiveness_seed import WINDOW_END, WINDOW_START, seed_effectiveness_store

runner = CliRunner()

# V50/V51 source tables telemetry must never mutate (refinement #4).
_SOURCE_TABLES = [
    "candidate_lifecycle_events",
    "candidate_source_refs",
    "candidate_merge_links",
    "candidate_suppression_rules",
    "daily_brief_ranking_runs",
    "daily_brief_ranked_candidates",
    "candidate_similarity_edges",
    "daily_brief_assembly_runs",
    "daily_brief_assembly_sections",
]
_V52_TABLES = [
    "daily_brief_exposure_events",
    "daily_brief_item_outcome_events",
    "ranking_policy_eval_runs",
    "ranking_policy_eval_items",
    "model_profile_eval_results",
    "brief_effectiveness_rollups",
]


def _invoke(db: str, *args: str):
    return runner.invoke(
        app,
        ["daily-brief", "evaluate-effectiveness", "--db", db, *args],
    )


def _table_fingerprint(db: str, tables: list[str]) -> dict[str, str]:
    """Content fingerprint (count + ordered-row hash) of each table."""
    conn = sqlite3.connect(db)
    out: dict[str, str] = {}
    for t in tables:
        rows = conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()
        blob = repr(rows).encode("utf-8")
        out[t] = f"{len(rows)}:{hashlib.sha256(blob).hexdigest()[:16]}"
    conn.close()
    return out


def test_dry_run_writes_zero_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_effectiveness_store(db)
    res = _invoke(
        db, "--window-start", WINDOW_START, "--window-end", WINDOW_END, "--eval-mode", "ablation"
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["applied"] is False
    counts = _table_fingerprint(db, _V52_TABLES)
    assert all(c.startswith("0:") for c in counts.values())


def test_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_effectiveness_store(db)
    res = _invoke(db, "--apply")
    assert res.exit_code == 2
    assert json.loads(res.stdout)["error"] == "apply_requires_max_persist"


def test_invalid_window_exits_2(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_effectiveness_store(db)
    res = _invoke(db, "--window-start", "2026-06-30", "--window-end", "2026-06-01")
    assert res.exit_code == 2
    res2 = _invoke(db, "--window-start", "not-a-date")
    assert res2.exit_code == 2


def test_invalid_eval_mode_exits_2(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_effectiveness_store(db)
    res = _invoke(db, "--eval-mode", "bogus")
    assert res.exit_code == 2


def test_apply_cap_exceeded_fails_closed_exit_3(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_effectiveness_store(db)
    res = _invoke(
        db,
        "--window-start",
        WINDOW_START,
        "--window-end",
        WINDOW_END,
        "--apply",
        "--max-persist",
        "2",
    )
    assert res.exit_code == 3
    payload = json.loads(res.stdout)
    assert payload["status"] == "fail_closed"
    assert "max_persist_exceeded" in payload["fail_closed_reason"]
    # Nothing persisted on a fail-closed cap.
    assert all(c.startswith("0:") for c in _table_fingerprint(db, _V52_TABLES).values())


def test_apply_persists_and_does_not_mutate_v50_v51(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_effectiveness_store(db)
    before = _table_fingerprint(db, _SOURCE_TABLES)
    res = _invoke(
        db,
        "--window-start",
        WINDOW_START,
        "--window-end",
        WINDOW_END,
        "--apply",
        "--max-persist",
        "500",
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["applied"] is True
    assert payload["persistence"]["persisted_total"] > 0
    after = _table_fingerprint(db, _SOURCE_TABLES)
    assert after == before  # telemetry mutated NONE of the V50/V51 source tables
    # V52 telemetry rows were written, all guard columns zero.
    conn = sqlite3.connect(db)
    for t in _V52_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        guards = [c for c in cols if c.endswith("_persisted") or c.endswith("_performed")]
        expr = "+".join(f"COALESCE(SUM({g}),0)" for g in guards)
        assert conn.execute(f"SELECT {expr} FROM {t}").fetchone()[0] == 0


def test_apply_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_effectiveness_store(db)
    args = (
        "--window-start",
        WINDOW_START,
        "--window-end",
        WINDOW_END,
        "--apply",
        "--max-persist",
        "500",
    )
    _invoke(db, *args)
    fp = _table_fingerprint(db, _V52_TABLES)
    res2 = _invoke(db, *args)
    assert res2.exit_code == 0
    assert _table_fingerprint(db, _V52_TABLES) == fp  # re-apply writes nothing new


def test_json_output_is_scanner_clean(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_effectiveness_store(db)
    res = _invoke(db, "--window-start", WINDOW_START, "--window-end", WINDOW_END)
    assert res.exit_code == 0
    assert scan_text_for_forbidden(res.stdout) == []
    payload = json.loads(res.stdout)
    assert payload["raw_safety"]["raw_free"] is True
    # /tmp DB path is surfaced (not a private home path) so the operator can confirm a copy was used.
    assert payload["db_indicator"][0] == "explicit_db"


def test_no_ranked_briefs_is_exit_0(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    from hb_assistant.construction.store import ConstructionStore

    ConstructionStore(db_path=db)  # migrate, but seed nothing
    res = _invoke(db, "--window-start", WINDOW_START, "--window-end", WINDOW_END)
    assert res.exit_code == 0
    assert json.loads(res.stdout)["status"] == "no_ranked_briefs"
