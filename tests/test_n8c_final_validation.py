"""N8C-21 — consolidated final validation of the whole N8C second-brain stack (N8C-1…N8C-20).

The FIRST test that asserts, in one place, that a fresh empty DB migrates to the current head and carries EVERY
N8C-owned table across the V100…V111 span (claims → enrichment → context-pack → memory → decision/preference/
open-loop → review → intelligence → research-packet → answer-draft → feedback → action-stage → quality). This
is a redeploy-readiness gate: a fresh NAS DB (or a migrated production DB) must land at exactly this schema
posture. Non-destructive: builds only a temp DB and reads it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

# One or more anchor tables per N8C phase family. Every one must exist in a fresh-migrated DB. Grouped so a
# failure names the phase whose migration regressed.
N8C_TABLE_ANCHORS: dict[str, tuple[str, ...]] = {
    "N8C-4 claims": ("assistant_claims", "assistant_claim_events"),
    "N8C-5 enrichment": ("assistant_enrichment_jobs", "assistant_enrichment_receipts"),
    "N8C-6 context-packs": ("assistant_context_packs", "assistant_context_pack_items",
                            "assistant_context_pack_receipts", "assistant_context_pack_events"),
    "N8C-7 memory": ("assistant_memory_nodes", "assistant_memory_mentions",
                     "assistant_memory_compilations", "assistant_memory_events"),
    "N8C-8 decision/preference/open-loop": ("assistant_decision_records", "assistant_preference_records",
                                            "assistant_open_loop_records", "assistant_decision_memory_events"),
    "N8C-9 review": ("assistant_review_items", "assistant_review_dispositions", "assistant_review_events"),
    "N8C-10 intelligence": ("assistant_intelligence_projections", "assistant_intelligence_projection_items",
                            "assistant_intelligence_projection_receipts",
                            "assistant_intelligence_projection_events"),
    "N8C-11 research-packets": ("assistant_research_packets", "assistant_research_packet_items",
                                "assistant_research_packet_citations", "assistant_research_packet_receipts",
                                "assistant_research_packet_events"),
    "N8C-14 answer-drafts": ("assistant_answer_drafts", "assistant_answer_draft_sections",
                             "assistant_answer_draft_citations", "assistant_answer_draft_receipts",
                             "assistant_answer_draft_events"),
    "N8C-18 feedback": ("assistant_feedback_records", "assistant_feedback_targets",
                        "assistant_feedback_recommendations", "assistant_feedback_receipts",
                        "assistant_feedback_events"),
    "N8C-19 action-stage": ("assistant_action_stages", "assistant_action_stage_items",
                            "assistant_action_stage_citations", "assistant_action_stage_receipts",
                            "assistant_action_stage_events"),
    "N8C-20 quality": ("assistant_quality_runs", "assistant_quality_findings", "assistant_quality_targets",
                       "assistant_quality_receipts", "assistant_quality_events"),
}


def _tables(db: Path) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def test_fresh_db_migrates_to_head(tmp_path: Path) -> None:
    db = tmp_path / "final.db"
    head = SQLiteMigrator(db_path=str(db)).apply()
    assert head == LATEST_SCHEMA_VERSION == 111


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "final.db"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION


def test_all_n8c_tables_present(tmp_path: Path) -> None:
    db = tmp_path / "final.db"
    SQLiteMigrator(db_path=str(db)).apply()
    present = _tables(db)
    missing: dict[str, list[str]] = {}
    for phase, anchors in N8C_TABLE_ANCHORS.items():
        gone = [t for t in anchors if t not in present]
        if gone:
            missing[phase] = gone
    assert not missing, f"missing N8C tables: {missing}"


def test_assistant_table_count_floor(tmp_path: Path) -> None:
    db = tmp_path / "final.db"
    SQLiteMigrator(db_path=str(db)).apply()
    assistant = {t for t in _tables(db) if t.startswith("assistant_")}
    # 48 phase-owned assistant tables + assistant_runs; a floor, not an exact match, so future additive N8C
    # phases don't break this gate.
    assert len(assistant) >= 48, len(assistant)


def test_schema_migrations_records_every_version(tmp_path: Path) -> None:
    db = tmp_path / "final.db"
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as c:
        versions = {r[0] for r in c.execute("SELECT version FROM schema_migrations")}
        head = c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    # every N8C schema version V100..V111 is recorded, and the head equals the code constant
    assert set(range(100, 112)) <= versions
    assert head == LATEST_SCHEMA_VERSION


def test_prior_rows_survive_reapply(tmp_path: Path) -> None:
    # A row written after migration survives a second (idempotent) migrate — no table is dropped/rewritten.
    db = tmp_path / "final.db"
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_quality_runs (quality_run_id, target_kind, target_id) "
                  "VALUES ('survive','feedback','f1')")
        c.commit()
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT target_kind FROM assistant_quality_runs WHERE quality_run_id='survive'"
                        ).fetchone()
    assert row == ("feedback",)
