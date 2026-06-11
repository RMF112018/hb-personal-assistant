"""Phase 10 V51 — daily-brief assembly orchestration tests.

Verifies deterministic section assembly, the degraded/withheld banner, dry-run = zero writes, apply
requires a cap and is idempotent, all new guard columns stay zero, and no raw content appears in
any output. Also confirms the deterministic ranked brief survives a withheld/unsafe model layer.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai.contracts import load_local_model_profiles
from hb_assistant.construction.second_brain.local_ai.daily_brief_assembly import (
    run_candidate_ranking_and_assembly,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.retrieval.embedder import DeterministicEmbedder
from tests._phase_10_ranking_seed import BRIEF_DATE, NOW, accept_task, seed_ranking_store

_V51_TABLES = [
    "daily_brief_ranking_runs",
    "daily_brief_ranked_candidates",
    "candidate_similarity_edges",
    "daily_brief_assembly_runs",
    "daily_brief_assembly_sections",
]


def _run(db: str, **kw):
    return run_candidate_ranking_and_assembly(
        store=seed_ranking_store(db),
        brief_date=BRIEF_DATE,
        now_utc=NOW,
        embedder=DeterministicEmbedder(),
        **kw,
    )


def test_no_client_is_success_deterministic(tmp_path: Path) -> None:
    res = _run(str(tmp_path / "t.sqlite"), use_model=False)
    assert res["status"] == "ok"
    assert res["ranking"]["model_status"] == "withheld"
    assert res["ranking"]["deterministic_fallback_used"] is True
    assert res["ranking"]["ranked_count"] == 3
    assert res["assembly"]["sections"]


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _run(db, use_model=False, dry_run=True)
    conn = sqlite3.connect(db)
    for table in _V51_TABLES:
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    conn.close()


def test_apply_requires_max_persist(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _run(str(tmp_path / "t.sqlite"), use_model=False, dry_run=False, max_persist=None)


def test_apply_persists_and_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    r1 = _run(db, use_model=False, dry_run=False, max_persist=500)
    assert r1["persistence"]["persisted_ranked"] == 3
    conn = sqlite3.connect(db)
    n1 = conn.execute("SELECT count(*) FROM daily_brief_ranked_candidates").fetchone()[0]
    # Re-apply same inputs → no duplicate rows.
    _run(db, use_model=False, dry_run=False, max_persist=500)
    n2 = conn.execute("SELECT count(*) FROM daily_brief_ranked_candidates").fetchone()[0]
    assert n1 == n2 == 3
    conn.close()


def test_all_guard_columns_zero_after_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _run(db, use_model=False, dry_run=False, max_persist=500)
    conn = sqlite3.connect(db)
    for table in _V51_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        guards = [c for c in cols if c.endswith("_persisted") or c.endswith("_performed")]
        total = "+".join(f"COALESCE(SUM({g}),0)" for g in guards)
        assert conn.execute(f"SELECT {total} FROM {table}").fetchone()[0] == 0
    conn.close()


def test_degraded_banner_when_source_missing(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_ranking_store(db)
    accept_task(store, "noref", refs=False, project_key="PRJ-Z")
    res = run_candidate_ranking_and_assembly(
        store=store, brief_date=BRIEF_DATE, now_utc=NOW, use_model=False
    )
    # Accepted-missing-source lowers coverage; assembly carries an honest degraded section.
    assert res["ranking"]["source_ref_coverage"] < 1.0
    keys = {s["section_key"] for s in res["assembly"]["sections"]}
    assert "data_gaps_degraded" in keys


def test_unsafe_model_preserves_deterministic_fallback(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    profiles = load_local_model_profiles()
    profile = next(p for p in profiles.profiles if p.profile_id == "default_extract")
    leak = json.dumps({"items": [{"alias": "c1", "why_this_matters": "open https://x.example/s"}]})
    res = run_candidate_ranking_and_assembly(
        store=seed_ranking_store(db),
        brief_date=BRIEF_DATE,
        now_utc=NOW,
        use_model=True,
        profile=profile,
        profiles=profiles,
        backend=StaticOutputClient(leak),
    )
    assert res["ranking"]["model_status"] == "withheld"
    assert res["ranking"]["deterministic_fallback_used"] is True
    assert res["ranking"]["ranked_count"] == 3  # deterministic ranked brief preserved


def test_output_has_no_raw_content(tmp_path: Path) -> None:
    res = _run(str(tmp_path / "t.sqlite"), use_model=False, dry_run=False, max_persist=500)
    blob = json.dumps(res).lower()
    for forbidden in ("http://", "https://", "@", "bearer", "secret", "body_html", "raw_body"):
        assert forbidden not in blob
