"""The deterministic family fixtures must seed records their exact-ID getters can then read.

Guards the connector re-test gap where family getters were untestable for lack of seeded data.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.obsidian_mcp.quality_repository import QualityRepository
from hb_assistant.store.migrator import SQLiteMigrator
from tests.second_brain_fixtures import seed_self_contained_families


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "fixtures.db")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_seeded_feedback_getter_returns_record(tmp_path: Path) -> None:
    db = _db(tmp_path)
    ids = seed_self_contained_families(db)
    rec = FeedbackRepository(db).get_feedback(ids["feedback"])
    assert rec is not None and rec["feedback_id"] == ids["feedback"]


def test_seeded_quality_getter_returns_record(tmp_path: Path) -> None:
    db = _db(tmp_path)
    ids = seed_self_contained_families(db)
    run = QualityRepository(db).get_quality_run(ids["quality"])
    assert run is not None and run["quality_run_id"] == ids["quality"]
